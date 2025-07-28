import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { v4 as uuid } from 'uuid';

const API_BASE = '<YOUR_API_GATEWAY_BASE>'; // es: https://xyz.execute-api.eu-central-1.amazonaws.com/prod
const PACS_BASE = '<YOUR_PACS_API_BASE>';   // es: https://abc-123.eu-central-1.elb.amazonaws.com

function App() {
  const [clientId, setClientId] = useState(null);
  const [queueUrl, setQueueUrl] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState('idle');
  const [result, setResult] = useState(null);
  // parametri PACS
  const [studyId,   setStudyId]   = useState('liver1/phantomx_abdomen_pelvis_dataset/D55-01');
  const [seriesId,  setSeriesId]  = useState('300/AiCE_BODY-SHARP_300_172938.900');
  const [imageId,   setImageId]   = useState('IM-0135-0001.dcm');
  const [scope,     setScope]     = useState('image');
  const [previewUrl,setPreviewUrl]= useState(null);

  async function provision() {
    const cid = uuid();
    setStatus('provisioning');
    const res = await fetch(`${API_BASE}/provision`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({client_id: cid})
    });
    const j = await res.json();
    setClientId(j.client_id);
    setQueueUrl(j.queue_url);
    setStatus('ready');
  }

  async function startJob() {
    const jid = uuid();
    setJobId(jid);
    setStatus('waiting');
    await fetch(`${API_BASE}/process/processing_1`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        job_id: jid,
        pacs: {
          study_id,
          series_id,
          image_id,
          scope
        },
        callback: { client_id: clientId }
      })
    });
    pollResult(jid);
  }

  async function pollResult(jid) {
    // semplice polling via fetch a un proxy (qui assumiamo CORS permesso)
    while(true) {
      const sqsRes = await fetch(`${API_BASE}/proxy-sqs?queue=${encodeURIComponent(queueUrl)}`);
      const msgs = await sqsRes.json();
      if(msgs.length) {
        const m = msgs.find(m=>m.job_id===jid);
        if(m) { setResult(m); setStatus('done'); return; }
      }
      await new Promise(r=>setTimeout(r,2000));
    }
  }

  return (
    <div style={{padding:20}}>
      <h1>🖼️ Test Pipeline</h1>
      {status==='idle' &&
        <>
          <button onClick={provision}>Provisiona coda</button>
          <div style={{margin:'1em 0'}}>
            <h2>📂 Anteprima PACS</h2>
            <div>
              <label>Study ID:</label>
              <input value={studyId} onChange={e=>setStudyId(e.target.value)} style={{width:'100%'}}/>
            </div>
            <div>
              <label>Series ID:</label>
              <input value={seriesId} onChange={e=>setSeriesId(e.target.value)} style={{width:'100%'}}/>
            </div>
            <div>
              <label>Image ID:</label>
              <input value={imageId} onChange={e=>setImageId(e.target.value)} style={{width:'100%'}}/>
            </div>
            <div>
              <label>Scope:</label>
              <input value={scope} onChange={e=>setScope(e.target.value)} style={{width:'100%'}}/>
            </div>
            <button onClick={async()=>{
                const res = await fetch(
                  `${PACS_BASE}/studies/${encodeURIComponent(studyId)}`+
                  `/images/${encodeURIComponent(seriesId)}`+
                  `/${encodeURIComponent(imageId)}`, {
                    headers:{'Accept':'application/json'}
                  });
                const j = await res.json();
                setPreviewUrl(j.url);
              }}>
              Carica Anteprima
            </button>
            {previewUrl && <div style={{marginTop:10}}>
              <h3>Anteprima:</h3>
              <img src={previewUrl} alt="PACS preview" style={{maxWidth:'100%'}}/>
            </div>}
          </div>
        </>
      }
      {status==='ready' &&
        <button onClick={startJob}>Avvia processing</button>
      }
      {status==='waiting' && <p>In attesa del risultato…</p>}
      {status==='done' &&
        <div>
          <h2>✅ Risultato Processato</h2>
          <img src={result.dicom.url} alt="Processed result" style={{maxWidth:'100%'}}/>
        </div>
      }
    </div>
  );
}

const root = createRoot(document.getElementById('root'));
root.render(<App/>);
