#!/usr/bin/env python3
"""Simple health check for ECS"""
import sys
import os

def health_check():
    """Basic health check - verify binary exists and environment is set"""
    try:
        binary_path = os.path.join(os.path.dirname(__file__), 'bin', 'grayscale')
        if not os.path.exists(binary_path):
            print("ERROR: Grayscale binary not found")
            return False
            
        # Check if we can import required modules
        import boto3
        
        print("Health check passed")
        return True
        
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

if __name__ == "__main__":
    if health_check():
        sys.exit(0)
    else:
        sys.exit(1)
