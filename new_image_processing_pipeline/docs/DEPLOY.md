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

        # ricostruisci tutte le immagini algoritmo, dovrebbe bastare il comando sopra perchè abbiamo aggiunto il meccanismo per prendere sempre immagini nuove
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

3. **Ricapitolando**

   Comandi essenziali da eseguire nella root di `new_image_processing_pipeline`:

   ```sh
      docker build -t mip-base -f containers/base/Dockerfile .
   ```

   Per effettuare il deploy degli stack (utilizzando sempre le immagini più aggiornate):

   ```sh
   cd infra
   cdk deploy --all --require-approval never
   ```

**Nota:**
- Ogni modifica a Dockerfile o codice richiede un nuovo build all'immagine base e deploy.
