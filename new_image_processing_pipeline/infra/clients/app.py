#!/usr/bin/env python3
import os
import sys
from aws_cdk import App
from client_stack import ClientResultsStack

# Parametri da environment o sys.argv
client_id = os.environ.get("CLIENT_ID") or (sys.argv[1] if len(sys.argv) > 1 else None)
topic_arn = os.environ.get("TOPIC_ARN") or (sys.argv[2] if len(sys.argv) > 2 else None)

if not client_id or not topic_arn:
    print("Usage: app.py <client_id> <topic_arn>")
    sys.exit(1)

app = App()
ClientResultsStack(app, "ClientResultsStack", client_id=client_id, topic_arn=topic_arn)
app.synth()
