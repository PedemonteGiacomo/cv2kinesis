import json, os, boto3, re
from decimal import Decimal
from botocore.exceptions import ClientError
import jwt
import requests
from jwt.algorithms import RSAAlgorithm
from typing import Dict, Any, Optional

dynamodb = boto3.resource("dynamodb")
lambda_client = boto3.client("lambda")
ssm_client = boto3.client("ssm")
TABLE = os.environ["ALGO_TABLE"]
PROVISIONER_ARN = os.environ["PROVISIONER_ARN"]

# Cognito configuration
USER_POOL_ID_PARAM = os.environ.get('USER_POOL_ID_PARAM', '/mip/admin/user-pool-id')
USER_POOL_REGION = os.environ.get('USER_POOL_REGION', 'us-east-1')

# Cache for User Pool ID and public keys
_user_pool_id_cache = None
_jwks_cache = None

def get_user_pool_id():
    """Retrieve and cache User Pool ID from SSM Parameter Store"""
    global _user_pool_id_cache
    
    if _user_pool_id_cache is None:
        try:
            response = ssm_client.get_parameter(Name=USER_POOL_ID_PARAM)
            _user_pool_id_cache = response['Parameter']['Value']
        except Exception as e:
            print(f"Error retrieving User Pool ID from SSM: {e}")
            # Fallback to environment variable if SSM fails
            _user_pool_id_cache = os.environ.get('USER_POOL_ID', '')
    
    return _user_pool_id_cache

def get_cognito_issuer():
    """Get Cognito issuer URL"""
    user_pool_id = get_user_pool_id()
    return f"https://cognito-idp.{USER_POOL_REGION}.amazonaws.com/{user_pool_id}"

def get_cognito_public_keys():
    """Retrieve and cache Cognito public keys for JWT verification"""
    global _jwks_cache
    
    if _jwks_cache is None:
        try:
            cognito_issuer = get_cognito_issuer()
            jwks_url = f"{cognito_issuer}/.well-known/jwks.json"
            response = requests.get(jwks_url, timeout=5)
            response.raise_for_status()
            _jwks_cache = response.json()
        except Exception as e:
            print(f"Error fetching JWKS: {str(e)}")
            raise Exception("Unable to fetch Cognito public keys")
    
    return _jwks_cache

def verify_cognito_token(token: str) -> Dict[str, Any]:
    """Verify and decode Cognito JWT token"""
    try:
        # Get the token header
        header = jwt.get_unverified_header(token)
        kid = header.get('kid')
        
        if not kid:
            raise Exception("Token missing 'kid' in header")
        
        # Get public keys
        jwks = get_cognito_public_keys()
        
        # Find the correct key
        public_key = None
        for key in jwks.get('keys', []):
            if key.get('kid') == kid:
                public_key = RSAAlgorithm.from_jwk(key)
                break
        
        if not public_key:
            raise Exception(f"Public key not found for kid: {kid}")
        
        # Verify and decode the token
        payload = jwt.decode(
            token,
            public_key,
            algorithms=['RS256'],
            issuer=get_cognito_issuer(),
            options={
                "verify_signature": True,
                "verify_iss": True,
                "verify_aud": False,  # Access tokens don't have aud claim
                "verify_exp": True
            }
        )
        
        # Verify token use
        if payload.get('token_use') != 'access':
            raise Exception("Token must be an access token")
        
        return payload
        
    except jwt.ExpiredSignatureError:
        raise Exception("Token has expired")
    except jwt.InvalidTokenError as e:
        raise Exception(f"Invalid token: {str(e)}")
    except Exception as e:
        raise Exception(f"Token verification failed: {str(e)}")

def authenticate_request(event: Dict[str, Any]) -> Dict[str, Any]:
    """Authenticate request using Cognito JWT token"""
    headers = event.get("headers", {})
    
    # Get Authorization header
    auth_header = headers.get("Authorization") or headers.get("authorization")
    if not auth_header:
        raise Exception("Missing Authorization header")
    
    # Extract Bearer token
    if not auth_header.startswith("Bearer "):
        raise Exception("Authorization header must start with 'Bearer '")
    
    token = auth_header[7:]  # Remove "Bearer " prefix
    
    # Verify the token
    payload = verify_cognito_token(token)
    
    return payload

def check_user_permissions(user_payload: Dict[str, Any], required_permission: str) -> bool:
    """Check if user has required permissions based on Cognito groups"""
    # Get user groups from token
    user_groups = user_payload.get('cognito:groups', [])
    
    # Permission mapping
    permissions = {
        'read': ['Administrators', 'Users'],  # Both groups can read
        'write': ['Administrators'],          # Only admins can write
        'admin': ['Administrators']           # Only admins for admin operations
    }
    
    allowed_groups = permissions.get(required_permission, [])
    
    # Check if user has any of the required groups
    return any(group in user_groups for group in allowed_groups)

def authorize_request(event: Dict[str, Any], required_permission: str) -> Dict[str, Any]:
    """Authenticate and authorize request"""
    try:
        user_payload = authenticate_request(event)
        
        # Check permissions
        if not check_user_permissions(user_payload, required_permission):
            groups = user_payload.get('cognito:groups', [])
            raise Exception(f"Insufficient permissions. User groups: {groups}, Required: {required_permission}")
        
        return user_payload
        
    except Exception as e:
        raise PermissionError(f"Authorization failed: {str(e)}")

def _resp(code, body):
    def decimal_default(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError
    return {
        "statusCode": code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization",
            "Access-Control-Allow-Methods": "GET,POST,PATCH,DELETE,OPTIONS",
        },
        "body": json.dumps(body, default=decimal_default),
    }

def _require_admin(event):
    """Authenticate user and require admin permissions"""
    try:
        payload = authorize_request(event, 'admin')
        return payload
    except Exception as e:
        raise PermissionError(f"Admin authentication failed: {str(e)}")

def _require_read(event):
    """Authenticate user and require read permissions"""
    try:
        payload = authorize_request(event, 'read')
        return payload
    except Exception as e:
        raise PermissionError(f"Read authentication failed: {str(e)}")

def _require_write(event):
    """Authenticate user and require write permissions"""
    try:
        payload = authorize_request(event, 'write')
        return payload
    except Exception as e:
        raise PermissionError(f"Write authentication failed: {str(e)}")

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
        # Handle CORS preflight requests
        if event.get("httpMethod") == "OPTIONS":
            return {
                "statusCode": 200,
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type,Authorization",
                    "Access-Control-Allow-Methods": "GET,POST,PATCH,DELETE,OPTIONS",
                },
                "body": ""
            }
        
        table = dynamodb.Table(TABLE)
        route = event["resource"]         # es: /admin/algorithms o /admin/algorithms/{id}
        method = event["httpMethod"]

        # Route: POST /admin/algorithms (Create algorithm - Admin only)
        if route.endswith("/admin/algorithms") and method == "POST":
            user_payload = _require_write(event)  # Admin permission required
            
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

        # Route: GET /admin/algorithms (List algorithms - Read permission)
        if route.endswith("/admin/algorithms") and method == "GET":
            user_payload = _require_read(event)  # Both admin and users can read
            
            resp = table.scan(Limit=200)
            return _resp(200, {"items": resp.get("Items", [])})

        # Routes for specific algorithms
        if "/admin/algorithms/" in route:
            algo_id = event["pathParameters"]["algo_id"]
            _validate_algo_id(algo_id)

            # Route: GET /admin/algorithms/{id} (Get algorithm details - Read permission)
            if method == "GET":
                user_payload = _require_read(event)  # Both admin and users can read
                
                item = table.get_item(Key={"algorithm_id": algo_id}).get("Item")
                if not item:
                    return _resp(404, {"error": "not found"})
                return _resp(200, item)

            # Route: PATCH /admin/algorithms/{id} (Update algorithm - Write permission)
            if method == "PATCH":
                user_payload = _require_write(event)  # Admin only
                
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

            # Route: DELETE /admin/algorithms/{id} (Delete algorithm - Write permission)
            if method == "DELETE":
                user_payload = _require_write(event)  # Admin only
                
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
