import React, { useState } from 'react';
import { createRoot } from 'react-dom/client';
import { v4 as uuid } from 'uuid';

const API_BASE = '<YOUR_API_GATEWAY_BASE>'; // es: https://xyz.execute-api.eu-central-1.amazonaws.com/prod

function App() {
  const [clientId, setClientId] = useState(null);
  const [queueUrl, setQueueUrl] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState('idle');
  const [result, setResult] = useState(null);

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
          study_id: 'liver1/.../D55-01',
          series_id:'300/...',
          image_id:'IM-0135-0001.dcm',
          scope:'image'
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
        <button onClick={provision}>Provisiona coda</button>
      }
      {status==='ready' &&
        <button onClick={startJob}>Avvia processing</button>
      }
      {status==='waiting' && <p>In attesa del risultato…</p>}
      {status==='done' &&
        <div>
          <h2>Risultato:</h2>
          <pre>{JSON.stringify(result,null,2)}</pre>
        </div>
      }
    </div>
  );
}

const root = createRoot(document.getElementById('root'));
root.render(<App/>);
