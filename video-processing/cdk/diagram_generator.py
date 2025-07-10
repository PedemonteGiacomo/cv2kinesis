#!/usr/bin/env python3
"""
App CDK con generazione automatica del diagramma dell'architettura
Genera un diagramma compatto della pipeline:
📱 Webcam → 🎥 Kinesis → 🐳 ECS → 📦 S3 → 📨 SQS → 👁️ Consumer
"""
import aws_cdk as cdk

# Import CdkGraph e il plugin per i diagrammi
from aws_pdk.cdk_graph import CdkGraph, FilterPreset
from aws_pdk.cdk_graph_plugin_diagram import CdkGraphDiagramPlugin

from pipeline_stack import VideoPipelineStack

def main():
    app = cdk.App()

    # 1) Instanzia lo stack esistente
    VideoPipelineStack(
        app,
        "VideoPipelineStack",
        env=cdk.Environment(
            account="544547773663",
            region="eu-central-1"
        ),
    )

    # 2) Instanzia CdkGraph con i parametri per il plugin
    #
    # - defaults: definisce i valori di default per tutti i diagrammi
    #   (qui forziamo filterPlan = COMPACT, che mostra solo le risorse core
    #    senza quelle di basso livello)
    # - theme: tema "dark" (cambia in "light" se preferisci)
    #
    # - diagrams: lista di oggetti, ognuno con "name" e "title"
    graph = CdkGraph(
        app,
        plugins=[
            CdkGraphDiagramPlugin(
                defaults={
                    "filter_plan": {
                        # Usando "COMPACT" qui per mostrare solo risorse principali
                        "preset": FilterPreset.COMPACT,
                    },
                    # Tema di default per i diagrammi
                    "theme": "dark",
                    # Layout direction: "horizontal", "vertical", "top-bottom", "left-right"
                    "layout": {
                        "direction": "left-right",  # o "top-bottom", "horizontal", "vertical"
                        "rankdir": "LR"  # LR=Left-Right, TB=Top-Bottom, BT=Bottom-Top, RL=Right-Left
                    }
                },
                diagrams=[
                    {
                        # Nome del primo diagramma
                        "name": "video-pipeline-architecture",
                        "title": "Video Pipeline Architecture - Real-time Object Detection",
                        # Eredita filterPlan e theme dai defaults
                    },
                    {
                        # Secondo diagramma con vista completa
                        "name": "detailed-architecture", 
                        "title": "Detailed Infrastructure View",
                        "filter_plan": {
                            "preset": FilterPreset.NON_EXTRANEOUS,
                        },
                    }
                ]
            )
        ],
    )

    # 3) CDK synth e generazione del diagramma
    app.synth()
    graph.report()

if __name__ == "__main__":
    main()
