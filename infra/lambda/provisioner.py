import os, json, boto3, time
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
sqs      = boto3.client("sqs")
ecs      = boto3.client("ecs")
iam      = boto3.client("iam")
ec2      = boto3.client("ec2")
logs     = boto3.client("logs")

TABLE            = os.environ["ALGO_TABLE"]
CLUSTER_NAME     = os.environ["ECS_CLUSTER_NAME"]
VPC_ID           = os.environ["VPC_ID"]
SUBNETS          = json.loads(os.environ["SUBNETS_JSON"])      # ["subnet-...","subnet-..."]
SECURITY_GROUP   = os.environ["SERVICE_SG"]
RESULTS_QUEUE    = os.environ["RESULTS_QUEUE_URL"]
OUTPUT_BUCKET    = os.environ["OUTPUT_BUCKET"]
PACS_API_BASE    = os.environ.get("PACS_API_URL","")
PACS_API_KEY     = os.environ.get("PACS_API_KEY","")
TASK_EXEC_ROLE   = os.environ["TASK_EXEC_ROLE_ARN"]            # pre-creato da CDK
TASK_ROLE        = os.environ["TASK_ROLE_ARN"]                 # pre-creato da CDK

def _queue_name(algo_id): return f"Requests-{algo_id}.fifo"
def _svc_name(algo_id):   return f"mip-{algo_id}"
def _log_group(algo_id):  return f"/ecs/mip-{algo_id}"

def _ensure_log_group(name):
    try:
        logs.create_log_group(logGroupName=name)
    except logs.exceptions.ResourceAlreadyExistsException:
        pass
    # retention 7 giorni
    logs.put_retention_policy(logGroupName=name, retentionInDays=7)

def _ensure_requests_queue(algo_id):
    qname = _queue_name(algo_id)
    resp = sqs.create_queue(
        QueueName=qname,
        Attributes={
            "FifoQueue": "true",
            "ContentBasedDeduplication": "true",
            "VisibilityTimeout": "900"
        }
    )
    return resp["QueueUrl"]

def _queue_arn(queue_url):
    a = boto3.client("sqs").get_queue_attributes(
        QueueUrl=queue_url, AttributeNames=["QueueArn"]
    )["Attributes"]["QueueArn"]
    return a

def _attach_queue_policy_to_taskrole(queue_arn):
    pol_name = "AllowReceiveFromAlgoQueues"
    stmt = {
        "Version":"2012-10-17",
        "Statement":[
            {
                "Effect":"Allow",
                "Action":[
                    "sqs:ReceiveMessage","sqs:DeleteMessage","sqs:GetQueueAttributes","sqs:ChangeMessageVisibility"
                ],
                "Resource": queue_arn
            }
        ]
    }
    iam.put_role_policy(RoleName=TASK_ROLE.split("/")[-1], PolicyName=pol_name, PolicyDocument=json.dumps(stmt))

def _register_taskdef(algo_id, image_uri, cpu, memory, command, env_dict):
    _ensure_log_group(_log_group(algo_id))
    env = [
        {"name":"QUEUE_URL",    "value": env_dict.get("QUEUE_URL","")},
        {"name":"OUTPUT_BUCKET","value": OUTPUT_BUCKET},
        {"name":"ALGO_ID",      "value": algo_id},
        {"name":"PACS_API_BASE","value": PACS_API_BASE},
        {"name":"PACS_API_KEY", "value": PACS_API_KEY},
        {"name":"RESULT_QUEUE", "value": RESULTS_QUEUE},
    ]
    # merge extra env
    for k,v in (env_dict or {}).items():
        if k in ("QUEUE_URL",):  # già aggiunto sopra
            continue
        env.append({"name":k,"value":str(v)})

    resp = ecs.register_task_definition(
        family=f"mip-{algo_id}",
        networkMode="awsvpc",
        executionRoleArn=TASK_EXEC_ROLE,
        taskRoleArn=TASK_ROLE,
        requiresCompatibilities=["FARGATE"],
        cpu=str(cpu),
        memory=str(memory),
        containerDefinitions=[
            {
                "name":"processor",
                "image": image_uri,
                "essential": True,
                "command": command,
                "environment": env,
                "logConfiguration": {
                    "logDriver":"awslogs",
                    "options":{
                        "awslogs-group": _log_group(algo_id),
                        "awslogs-region": os.environ["AWS_REGION"],
                        "awslogs-stream-prefix": algo_id
                    }
                }
            }
        ]
    )
    return resp["taskDefinition"]["taskDefinitionArn"]

def _create_or_update_service(algo_id, taskdef_arn, desired):
    svc_name = _svc_name(algo_id)
    try:
        ecs.describe_services(cluster=CLUSTER_NAME, services=[svc_name])["services"][0]
        # update
        ecs.update_service(
            cluster=CLUSTER_NAME,
            service=svc_name,
            taskDefinition=taskdef_arn,
            desiredCount=int(desired),
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": SUBNETS,
                    "securityGroups": [SECURITY_GROUP],
                    "assignPublicIp":"ENABLED"
                }
            }
        )
        return "updated"
    except (IndexError, ecs.exceptions.ServiceNotFoundException, ClientError):
        # create
        ecs.create_service(
            cluster=CLUSTER_NAME,
            serviceName=svc_name,
            taskDefinition=taskdef_arn,
            desiredCount=int(desired),
            launchType="FARGATE",
            networkConfiguration={
                "awsvpcConfiguration": {
                    "subnets": SUBNETS,
                    "securityGroups": [SECURITY_GROUP],
                    "assignPublicIp": "ENABLED"
                }
            }
        )
        return "created"

def handler(event, _):
    action   = (event or {}).get("action","provision")
    algo_id  = event.get("algo_id")
    table    = dynamodb.Table(TABLE)

    item = table.get_item(Key={"algorithm_id": algo_id}).get("Item")
    if not item:
        return {"status":"error","message":"algo not found"}

    try:
        if action in ("provision","update"):
            # 1) queue
            qurl = _ensure_requests_queue(algo_id)
            qarn = _queue_arn(qurl)
            _attach_queue_policy_to_taskrole(qarn)

            # 2) taskdef
            env = dict(item.get("env") or {})
            env["QUEUE_URL"] = qurl
            tdef = _register_taskdef(
                algo_id=algo_id,
                image_uri=item["image_uri"],
                cpu=item.get("cpu",1024),
                memory=item.get("memory",2048),
                command=item.get("command") or ["/app/worker.sh"],
                env_dict=env,
            )

            # 3) service
            op = _create_or_update_service(algo_id, tdef, item.get("desired_count",1))

            # 4) persist
            table.update_item(
                Key={"algorithm_id": algo_id},
                UpdateExpression="SET #st=:a, resource_status=:r",
                ExpressionAttributeNames={"#st":"status"},
                ExpressionAttributeValues={
                    ":a":"ACTIVE",
                    ":r":{
                        "queue_url": qurl,
                        "queue_arn": qarn,
                        "task_definition": tdef,
                        "service": _svc_name(algo_id),
                    }
                }
            )
            return {"status":"ok","op":op}

        if action == "scale_down":
            # porta a 0 il servizio
            ecs.update_service(cluster=CLUSTER_NAME, service=_svc_name(algo_id), desiredCount=0)
            table.update_item(
                Key={"algorithm_id": algo_id},
                UpdateExpression="SET #st=:s",
                ExpressionAttributeNames={"#st":"status"},
                ExpressionAttributeValues={":s":"SCALED_DOWN"}
            )
            return {"status":"ok","op":"scaled_down"}

        if action == "delete_hard":
            # best-effort: scale to 0 + (facoltativo) delete service; non eliminiamo SQS per default
            try:
                ecs.update_service(cluster=CLUSTER_NAME, service=_svc_name(algo_id), desiredCount=0)
                time.sleep(2)
                ecs.delete_service(cluster=CLUSTER_NAME, service=_svc_name(algo_id), force=True)
            except Exception:
                pass
            table.update_item(
                Key={"algorithm_id": algo_id},
                UpdateExpression="SET #st=:s",
                ExpressionAttributeNames={"#st":"status"},
                ExpressionAttributeValues={":s":"DELETED"}
            )
            return {"status":"ok","op":"deleted"}

        return {"status":"error","message":"unknown action"}

    except Exception as e:
        table.update_item(
            Key={"algorithm_id": algo_id},
            UpdateExpression="SET #st=:s, last_error=:e",
            ExpressionAttributeNames={"#st":"status"},
            ExpressionAttributeValues={":s":"ERROR", ":e":str(e)}
        )
        raise
