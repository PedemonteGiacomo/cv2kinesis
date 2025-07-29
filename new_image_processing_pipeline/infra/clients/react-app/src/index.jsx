
import React, { useState } from 'react';
import DicomViewer from './DicomViewer';
import { createRoot } from 'react-dom/client';
import { v4 as uuid } from 'uuid';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import { Box, Grid, Card, CardContent, Typography, TextField, Button, Select, MenuItem, Alert, CircularProgress, Divider } from '@mui/material';

// Palette Esaote (https://www2.esaote.com/it-IT/)
const esaoteTheme = createTheme({
  palette: {
    primary: { main: '#e30613' }, // rosso Esaote
    secondary: { main: '#005fa3' }, // blu accent
    success: { main: '#4bb543' },
    background: { default: '#f5f7fa' },
    text: { primary: '#222', secondary: '#005fa3' }
  },
  typography: { fontFamily: 'Roboto, Arial, sans-serif' }
});

const API_BASE  = (process.env.REACT_APP_API_BASE || '<default>').replace(/\/$/, '');
const PACS_BASE = process.env.REACT_APP_PACS_BASE   || '<default>';

function App() {
  const [clientId, setClientId] = useState(null);
  const [queueUrl, setQueueUrl] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState('idle');
  const [result, setResult] = useState(null);
  const [studyId,   setStudyId]   = useState('liver1/phantomx_abdomen_pelvis_dataset/D55-01');
  const [seriesId,  setSeriesId]  = useState('300/AiCE_BODY-SHARP_300_172938.900');
  const [imageId,   setImageId]   = useState('IM-0135-0095.dcm');
  const [scope,     setScope]     = useState('image');
  const [previewUrl,setPreviewUrl]= useState(null);
  const [algorithm, setAlgorithm] = useState('processing_1');
  const [provisioned, setProvisioned] = useState(false);

  async function provision() {
    const cid = uuid();
    setStatus('provisioning');
    setResult(null); // reset risultato
    // provisioning sempre su /provision
    const res = await fetch(`${API_BASE}/provision`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({client_id: cid})
    });
    const j = await res.json();
    setClientId(j.client_id);
    setQueueUrl(j.queue_url);
    setProvisioned(true);
    setStatus('ready');
  }

  async function startJob() {
    const jid = uuid();
    setJobId(jid);
    setStatus('waiting');
    setResult(null); // reset risultato
    // Usa i valori dallo stato React
    const payload = {
      job_id: jid,
      pacs: {
        study_id: studyId,
        series_id: seriesId,
        image_id: imageId,
        scope: scope
      },
      callback: { client_id: clientId, queue_url: queueUrl }
    };
    console.log("Job payload:", payload);
    await fetch(`${API_BASE}/process/${algorithm}`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
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
    <ThemeProvider theme={esaoteTheme}>
      <Box sx={{ bgcolor: 'background.default', minHeight: '100vh', p: 3 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
          <img src="/esaote-logo.svg" alt="Esaote Logo" style={{height:40, marginRight:16}} />
          <Typography variant="h4" color="primary" fontWeight={700}>
            Test Pipeline
          </Typography>
        </Box>
        <Grid container spacing={4}>
          <Grid item xs={12} md={6}>
            <Card elevation={2} sx={{ mb: 2, borderTop: '6px solid #e30613' }}>
              <CardContent>
                <Typography variant="h6" color="primary" fontWeight={600} gutterBottom>
                  Anteprima PACS
                </Typography>
                <TextField label="Study ID" value={studyId} onChange={e=>setStudyId(e.target.value)} fullWidth margin="dense" size="small" />
                <TextField label="Series ID" value={seriesId} onChange={e=>setSeriesId(e.target.value)} fullWidth margin="dense" size="small" />
                <TextField label="Image ID" value={imageId} onChange={e=>setImageId(e.target.value)} fullWidth margin="dense" size="small" />
                <TextField label="Scope" value={scope} onChange={e=>setScope(e.target.value)} fullWidth margin="dense" size="small" />
                <Button variant="contained" color="primary" sx={{ mt: 2 }} onClick={async()=>{
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
                </Button>
                {previewUrl && (
                  <Box sx={{ mt: 3 }}>
                    <Typography variant="subtitle1" color="primary" fontWeight={500}>Originale DICOM:</Typography>
                    <DicomViewer url={previewUrl} />
                  </Box>
                )}
              </CardContent>
            </Card>
          </Grid>
          <Grid item xs={12} md={6}>
            <Card elevation={2} sx={{ mb: 2, borderTop: '6px solid #e30613' }}>
              <CardContent>
                {/* Sezione scelta algoritmo, provisioning, avvio processing */}
                <Box sx={{ mb: 2 }}>
                  <Typography variant="subtitle1" color="primary" fontWeight={500} gutterBottom>
                    Parametri immagine da processare
                  </Typography>
                  <TextField label="Study ID" value={studyId} onChange={e=>setStudyId(e.target.value)} fullWidth margin="dense" size="small" />
                  <TextField label="Series ID" value={seriesId} onChange={e=>setSeriesId(e.target.value)} fullWidth margin="dense" size="small" />
                  <TextField label="Image ID" value={imageId} onChange={e=>setImageId(e.target.value)} fullWidth margin="dense" size="small" />
                  <TextField label="Scope" value={scope} onChange={e=>setScope(e.target.value)} fullWidth margin="dense" size="small" />
                  <Button variant="outlined" color="primary" sx={{ mt: 1, mb: 2 }} onClick={async()=>{
                    setResult(null); // reset risultato
                    setProvisioned(false); // reset coda
                    setClientId(null);
                    setQueueUrl(null);
                    setStatus('idle');
                    const res = await fetch(
                      `${PACS_BASE}/studies/${encodeURIComponent(studyId)}`+
                      `/images/${encodeURIComponent(seriesId)}`+
                      `/${encodeURIComponent(imageId)}`, {
                        headers:{'Accept':'application/json'}
                      });
                    const j = await res.json();
                    setPreviewUrl(j.url);
                  }}>
                    Aggiorna anteprima
                  </Button>
                  <Divider sx={{ my: 2 }} />
                  <Typography variant="subtitle1" color="primary" fontWeight={500}>Algoritmo:</Typography>
                  <Select value={algorithm} onChange={e=>setAlgorithm(e.target.value)} fullWidth size="small" sx={{ mb: 2 }}>
                    <MenuItem value="processing_1">Processing 1</MenuItem>
                    <MenuItem value="processing_6">Processing 6</MenuItem>
                    {/* aggiungi altri algoritmi se necessario */}
                  </Select>
                  <Button variant="contained" color="primary" fullWidth disabled={provisioned || status==='provisioning'} onClick={provision} sx={{ mb: 2, bgcolor: '#e30613', color: '#fff', '&:hover': { bgcolor: '#b8000f' } }}>
                    {provisioned ? 'Coda provisionata' : (status==='provisioning' ? <><CircularProgress size={18} sx={{mr:1}}/> Provisioning...</> : 'Provisiona coda')}
                  </Button>
                  {(status==='ready' || status==='done') && (
                    <Button variant="contained" color="secondary" fullWidth onClick={startJob} sx={{ mb: 2, color: '#fff', fontWeight: 600 }}>Avvia processing</Button>
                  )}
                  {status==='waiting' && (
                    <Alert severity="info" sx={{ mb: 2 }}>⏳ In attesa del risultato…</Alert>
                  )}
                  {/* Sezione info coda provisionata */}
                  {provisioned && queueUrl && (
                    <Alert severity="success" sx={{ mb: 2 }}>
                      <strong>Coda provisionata!</strong><br/>
                      <span style={{fontSize:'0.95em'}}>Queue URL:</span><br/>
                      <span style={{fontFamily:'monospace', wordBreak:'break-all', color:'#005fa3'}}>{queueUrl}</span>
                    </Alert>
                  )}
                </Box>
                {/* Visualizzazione DICOM processato */}
                {result && result.dicom?.url ? (
                  <>
                    <Typography variant="h6" color="success.main" fontWeight={600} gutterBottom>
                      <span style={{verticalAlign:'middle'}}>✅</span> Risultato Processato
                    </Typography>
                    <DicomViewer url={result.dicom.url} />
                  </>
                ) : (
                  <Box sx={{ color: 'grey.500', mt: 2 }}>Nessun risultato ancora disponibile.</Box>
                )}
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      </Box>
    </ThemeProvider>
  );
}

const root = createRoot(document.getElementById('root'));
root.render(<App/>);
