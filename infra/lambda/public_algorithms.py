import json, os, boto3
from decimal import Decimal
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
TABLE = os.environ["ALGO_TABLE"]

def _resp(code, body):
    """Helper to create HTTP response with CORS headers"""
    def decimal_default(obj):
        if isinstance(obj, Decimal):
            return float(obj)
        raise TypeError
    
    return {
        "statusCode": code,
        "headers": {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,OPTIONS",
        },
        "body": json.dumps(body, default=decimal_default),
    }

def _filter_public_fields(algorithm):
    """Filter algorithm data to only include public fields"""
    public_fields = [
        'algorithm_id',
        'status', 
        'cpu',
        'memory',
        'desired_count',
        'name',
        'description',
        'version',
        'category',
        'tags'
    ]
    
    # Create filtered result with only public fields
    filtered = {}
    for field in public_fields:
        if field in algorithm:
            filtered[field] = algorithm[field]
    
    # Add computed fields for better UX
    if 'algorithm_id' in algorithm:
        # Use algorithm_id as name if no name is provided
        filtered['name'] = algorithm.get('name', algorithm['algorithm_id'])
        
    # Add user-friendly status
    status = algorithm.get('status', 'UNKNOWN').upper()
    if status in ['ACTIVE', 'RUNNING']:
        filtered['status'] = 'ACTIVE'
    elif status in ['INACTIVE', 'STOPPED']:
        filtered['status'] = 'INACTIVE'  
    elif status in ['PENDING', 'STARTING', 'REGISTERED']:
        filtered['status'] = 'PENDING'
    else:
        filtered['status'] = 'UNKNOWN'
        
    return filtered

def handler(event, context):
    """
    Public Lambda handler for read-only algorithm access
    
    Supported routes:
    - GET /algorithms - List all algorithms (public info only)
    - GET /algorithms/{id} - Get single algorithm (public info only)
    """
    try:
        # Handle CORS preflight requests
        if event.get("httpMethod") == "OPTIONS":
            return {
                "statusCode": 200,
                "headers": {
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Headers": "Content-Type",
                    "Access-Control-Allow-Methods": "GET,OPTIONS",
                },
                "body": ""
            }
        
        table = dynamodb.Table(TABLE)
        route = event.get("resource", "")
        method = event.get("httpMethod", "")
        
        # GET /algorithms - List all algorithms
        if route.endswith("/algorithms") and method == "GET":
            try:
                # Scan all algorithms from DynamoDB
                response = table.scan()
                algorithms = response.get("Items", [])
                
                # Filter to only include public fields and active/visible algorithms
                public_algorithms = []
                for algo in algorithms:
                    # Only include algorithms that are not in error states
                    status = algo.get('status', '').upper()
                    if status not in ['ERROR', 'FAILED', 'DELETED']:
                        public_algorithms.append(_filter_public_fields(algo))
                
                # Sort by algorithm_id for consistent ordering
                public_algorithms.sort(key=lambda x: x.get('algorithm_id', ''))
                
                return _resp(200, {
                    "items": public_algorithms,
                    "count": len(public_algorithms)
                })
                
            except Exception as e:
                print(f"Error listing algorithms: {str(e)}")
                return _resp(500, {
                    "error": "Errore nel caricamento degli algoritmi",
                    "message": "Si è verificato un errore durante il recupero della lista algoritmi"
                })
        
        # GET /algorithms/{id} - Get single algorithm
        if "/algorithms/" in route and method == "GET":
            try:
                # Extract algorithm ID from path
                path_params = event.get("pathParameters", {})
                algo_id = path_params.get("algo_id") if path_params else None
                
                if not algo_id:
                    return _resp(400, {
                        "error": "ID algoritmo mancante",
                        "message": "L'ID dell'algoritmo è richiesto"
                    })
                
                # Get algorithm from DynamoDB
                response = table.get_item(Key={"algorithm_id": algo_id})
                algorithm = response.get("Item")
                
                if not algorithm:
                    return _resp(404, {
                        "error": "Algoritmo non trovato", 
                        "message": f"L'algoritmo con ID '{algo_id}' non esiste"
                    })
                
                # Check if algorithm is visible to public
                status = algorithm.get('status', '').upper()
                if status in ['ERROR', 'FAILED', 'DELETED']:
                    return _resp(404, {
                        "error": "Algoritmo non disponibile",
                        "message": f"L'algoritmo con ID '{algo_id}' non è attualmente disponibile"
                    })
                
                # Return filtered public data
                return _resp(200, _filter_public_fields(algorithm))
                
            except Exception as e:
                print(f"Error getting algorithm {algo_id}: {str(e)}")
                return _resp(500, {
                    "error": "Errore nel caricamento dell'algoritmo",
                    "message": "Si è verificato un errore durante il recupero dell'algoritmo"
                })
        
        # Route not found
        return _resp(404, {
            "error": "Endpoint non trovato",
            "message": f"L'endpoint {method} {route} non esiste"
        })
        
    except Exception as e:
        print(f"Unhandled error in public algorithms handler: {str(e)}")
        return _resp(500, {
            "error": "Errore del server", 
            "message": "Si è verificato un errore interno del server"
        })
