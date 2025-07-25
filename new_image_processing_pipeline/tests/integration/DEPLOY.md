# Build e deploy stack (pipeline)

1. **Ricostruisci le immagini Docker**
   - Se usi make:
     ```sh
        make build-base
        make build-algos
     ```
   - Oppure manualmente:
     ```sh
        # ricostruisci l’immagine di base
        docker build -t mip-base -f containers/base/Dockerfile .
        # ricostruisci tutte le immagini algoritmo
        $algos = @("processing_1", "processing_6")
        foreach ($a in $algos) {
            docker build -t "mip-$a" -f "containers/$a/Dockerfile" .
        }
     ```

2. **Deploy CDK**
   - Da PowerShell o bash:
     ```sh
        cd infra
        cdk deploy ImgPipeline --require-approval never
        # oppure per tutti gli stack
        cdk deploy --all --require-approval never
     ```

3. **Verifica**
   - Controlla che i task ECS siano aggiornati e in running.
   - Puoi usare la console AWS ECS o:
     ```sh
     aws ecs list-tasks --cluster <cluster-name>
     aws ecs describe-tasks --cluster <cluster-name> --tasks <task-id>
     ```

**Nota:**
- Ogni modifica a Dockerfile o codice richiede un nuovo build e deploy.
- Se usi `from_asset` nel CDK, il deploy aggiorna automaticamente l'immagine su ECS.
