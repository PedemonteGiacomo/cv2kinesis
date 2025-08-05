import json, os, boto3, re
from decimal import Decimal
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")
TABLE = os.environ["ALGO_TABLE"]
ADMIN_KEY = os.environ.get("ADMIN_KEY", "")
PROVISIONER_ARN = os.environ["PROVISIONER_ARN"]

def _resp(code, body):
    def decimal_default(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError
    return {
        "statusCode": code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,x-admin-key",
        },
        "body": json.dumps(body, default=decimal_default),
    }

def _require_admin(event):
    hdrs = event.get("headers") or {}
    if hdrs.get("x-admin-key") != ADMIN_KEY:
        raise PermissionError("invalid admin key")

def _validate_algo_id(algo_id: str):
    if not re.match(r"^[a-z0-9_][a-z0-9_\-]{2,63}$", algo_id):
        raise ValueError("algo_id non valido: usare [a-z0-9_-], 3..64 char")

def _validate_spec(spec: dict):
    # campi minimi
    for k in ["algo_id", "image_uri"]:
        if k not in spec:
            raise ValueError(f"campo richiesto mancante: {k}")
    # defaults sicuri
    spec.setdefault("cpu", 1024)          # 0.5 vCPU
    spec.setdefault("memory", 2048)       # 2 GB
    spec.setdefault("desired_count", 1)
    spec.setdefault("command", ["/app/worker.sh"])
    spec.setdefault("env", {})
    return spec

def _invoke_provisioner(action: str, algo_id: str):
    payload = {"action": action, "algo_id": algo_id}
    lambda_client.invoke(
        FunctionName=PROVISIONER_ARN,
        InvocationType="Event",
        Payload=json.dumps(payload).encode(),
    )

def handler(event, _):
    try:
        _require_admin(event)
        table = dynamodb.Table(TABLE)
        route = event["resource"]         # es: /admin/algorithms o /admin/algorithms/{id}
        method = event["httpMethod"]

        if route.endswith("/admin/algorithms") and method == "POST":
            body = json.loads(event.get("body") or "{}")
            spec = _validate_spec(body)
            _validate_algo_id(spec["algo_id"])

            # upsert registro
            table.put_item(
                Item={
                    "algorithm_id": spec["algo_id"],
                    "status": "REGISTERED",
                    "image_uri": spec["image_uri"],
                    "cpu": int(spec["cpu"]),
                    "memory": int(spec["memory"]),
                    "desired_count": int(spec["desired_count"]),
                    "command": spec.get("command", ["/app/worker.sh"]),
                    "env": spec.get("env", {}),
                    "resource_status": {},
                },
                ConditionExpression="attribute_not_exists(algorithm_id)",
            )
            _invoke_provisioner("provision", spec["algo_id"])
            return _resp(202, {"message": "registered, provisioning started"})

        if route.endswith("/admin/algorithms") and method == "GET":
            resp = table.scan(Limit=200)
            return _resp(200, {"items": resp.get("Items", [])})

        if "/admin/algorithms/" in route:
            algo_id = event["pathParameters"]["algo_id"]
            _validate_algo_id(algo_id)

            if method == "GET":
                item = table.get_item(Key={"algorithm_id": algo_id}).get("Item")
                if not item:
                    return _resp(404, {"error": "not found"})
                return _resp(200, item)

            if method == "PATCH":
                body = json.loads(event.get("body") or "{}")
                # aggiorna campi consentiti
                expr, names, vals = [], {}, {}
                for k in ("image_uri", "cpu", "memory", "desired_count", "command", "env"):
                    if k in body:
                        expr.append(f"#{k} = :{k}")
                        names[f"#{k}"] = k
                        vals[f":{k}"] = body[k]
                if not expr:
                    return _resp(400, {"error": "niente da aggiornare"})
                table.update_item(
                    Key={"algorithm_id": algo_id},
                    UpdateExpression="SET " + ", ".join(expr),
                    ExpressionAttributeNames=names,
                    ExpressionAttributeValues=vals,
                )
                _invoke_provisioner("update", algo_id)
                return _resp(202, {"message": "update accepted"})

            if method == "DELETE":
                hard = (event.get("queryStringParameters") or {}).get("hard") == "true"
                table.update_item(
                    Key={"algorithm_id": algo_id},
                    UpdateExpression="SET #st = :s",
                    ExpressionAttributeNames={"#st": "status"},
                    ExpressionAttributeValues={":s": "DELETING" if hard else "SCALING_DOWN"},
                )
                _invoke_provisioner("delete_hard" if hard else "scale_down", algo_id)
                return _resp(202, {"message": "deletion/scale request accepted"})

        return _resp(404, {"error": "route not found"})

    except PermissionError as e:
        return _resp(403, {"error": str(e)})
    except ClientError as e:
        return _resp(400, {"error": e.response["Error"]["Message"]})
    except Exception as e:
        return _resp(500, {"error": str(e)})
