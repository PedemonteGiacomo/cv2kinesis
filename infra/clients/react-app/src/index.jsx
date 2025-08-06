
import React, { useState } from 'react';
import DicomMetaCard from './DicomMetaCard';
import { data as dcmjsData } from 'dcmjs';
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
const PACS_BASE = process.env.REACT_APP_PACS_API_BASE   || '<default>';
const WS_ENDPOINT = process.env.REACT_APP_WS_ENDPOINT || '<ws-endpoint>';


function App() {
  const [originalMeta, setOriginalMeta] = useState(null);
  const [processedMeta, setProcessedMeta] = useState(null);
  async function extractDicomMeta(url) {
    try {
      console.log('[extractDicomMeta] Fetching DICOM from:', url);
      const res = await fetch(url);
      if (!res.ok) {
        console.error('[extractDicomMeta] Fetch failed:', res.status, res.statusText);
        return null;
      }
      const arrayBuffer = await res.arrayBuffer();
      const dicomData = dcmjsData.DicomMessage.readFile(arrayBuffer);
      const dataset = dcmjsData.DicomMetaDictionary.naturalizeDataset(dicomData.dict);
      if (dicomData.dict['x00181030'] && !dataset.ProtocolName) {
        dataset.ProtocolName = dicomData.dict['x00181030'].Value?.[0] || '';
      }
      console.log('[extractDicomMeta] Estratti metadati:', dataset);
      return dataset;
    } catch (e) {
      console.error('[extractDicomMeta] Errore parsing DICOM:', e);
      return null;
    }
  }
  const [clientId, setClientId] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [status, setStatus] = useState('idle');
  const [result, setResult] = useState(null);
  const [wsError, setWsError] = useState(false);
  const [studyId,   setStudyId]   = useState('liver1/phantomx_abdomen_pelvis_dataset/D55-01');
  const [seriesId,  setSeriesId]  = useState('300/AiCE_BODY-SHARP_300_172938.900');
  const [imageId,   setImageId]   = useState('IM-0135-0095.dcm');
  const [scope,     setScope]     = useState('image');
  const [algorithm, setAlgorithm] = useState('');
  const [algorithms, setAlgorithms] = useState([]);
  // Fetch algorithms on mount
  React.useEffect(() => {
    async function fetchAlgorithms() {
      try {
        const res = await fetch(`${API_BASE}/admin/algorithms`, {
          headers: {
            'x-admin-key': process.env.REACT_APP_ADMIN_KEY || ''
          }
        });
        const data = await res.json();
        const activeAlgos = (data.items || []).filter(a => a.status === 'ACTIVE');
        setAlgorithms(activeAlgos);
        if (activeAlgos.length > 0) setAlgorithm(activeAlgos[0].algorithm_id);
      } catch (e) {
        setAlgorithms([]);
      }
    }
    fetchAlgorithms();
  }, []);
  const [ws, setWs] = useState(null);
  const [originalUrl, setOriginalUrl] = useState(null);

  // Auto-generate client_id on mount if not present
  React.useEffect(() => {
    if (!clientId) {
      // Genera client_id localmente invece di chiamare /provision
      const newClientId = uuid();
      setClientId(newClientId);
      console.log('[CLIENT] Generated client_id:', newClientId);
    }
  }, [clientId]);

  // WebSocket connessione/disconnessione con client_id, ricezione risultati push
  React.useEffect(() => {
    if (!clientId) return;
    let wsock;
    let pingInterval;
    let closed = false;
    wsock = new window.WebSocket(`${WS_ENDPOINT}?client_id=${encodeURIComponent(clientId)}`);
    setWs(wsock);
    wsock.onopen = () => {
      pingInterval = setInterval(() => {
        if (wsock.readyState === 1) wsock.send(JSON.stringify({type:'ping'}));
      }, 5*60*1000);
    };
    wsock.onmessage = ev => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.job_id && jobId && msg.job_id === jobId) {
          setResult(msg);
          setStatus('done');
          if (msg.dicom?.url) {
            extractDicomMeta(msg.dicom.url).then(meta => setProcessedMeta(meta));
          }
        }
      } catch {}
    };
    wsock.onclose = () => {
      clearInterval(pingInterval);
    };
    wsock.onerror = () => {
      wsock.close();
    };
    return () => {
      closed = true;
      if (wsock) wsock.close();
      clearInterval(pingInterval);
    };
    // eslint-disable-next-line
  }, [clientId, jobId]);

  async function startJob() {
    if (!clientId) {
      alert('Client non provisionato. Ricarica la pagina.');
      return;
    }
    const jid = uuid();
    setJobId(jid);
    setStatus('waiting');
    setResult(null);
    setWsError(false);
    setOriginalUrl(null);
    setOriginalMeta(null);
    setProcessedMeta(null);
    try {
      const res = await fetch(
        `${PACS_BASE}/studies/${encodeURIComponent(studyId)}`+
        `/images/${encodeURIComponent(seriesId)}`+
        `/${encodeURIComponent(imageId)}`,
        { headers: { 'Accept': 'application/json' } }
      );
      const j = await res.json();
      setOriginalUrl(j.url);
      if (j.url) {
        extractDicomMeta(j.url).then(setOriginalMeta);
      }
    } catch (e) {
      setOriginalUrl(null);
    }
    const payload = {
      job_id: jid,
      pacs: {
        study_id: studyId,
        series_id: seriesId,
        image_id: imageId,
        scope: scope
      },
      client_id: clientId
    };
    console.log("Job payload:", payload);
    await fetch(`${API_BASE}/process/${algorithm}`, {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(payload)
    });
    // La ricezione avviene via WebSocket
  }


  // ...rimosso: la ricezione push avviene ora nella stessa connessione WebSocket aperta su clientId...

  return (
    <ThemeProvider theme={esaoteTheme}>
      <Box sx={{
        bgcolor: 'linear-gradient(135deg, #f5f7fa 0%, #e3e9f6 100%)',
        minHeight: '100vh',
        p: 0,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
      }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 3, mt: 4 }}>
          <img src="/esaote-logo.svg" alt="Esaote Logo" style={{height:48, marginRight:20}} />
          <Typography variant="h3" color="primary" fontWeight={800} letterSpacing={1} sx={{textShadow:'0 2px 8px #fff8'}}>Image Processing Pipeline</Typography>
        </Box>
        <Card elevation={8} sx={{
          width: '100%',
          maxWidth: 1100,
          borderRadius: 5,
          boxShadow: '0 8px 32px 0 rgba(35,50,100,0.18)',
          background: 'linear-gradient(120deg, #fff 60%, #f5f7fa 100%)',
          borderTop: '8px solid #e30613',
          mb: 6,
        }}>
          <CardContent sx={{ p: 5 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', mb: 3 }}>
              <Box sx={{
                bgcolor: '#e30613',
                borderRadius: '50%',
                width: 54,
                height: 54,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                boxShadow: '0 2px 8px #e3061340',
                mr: 3,
                overflow: 'hidden',
              }}>
                <img src="/esaote_e.svg" alt="Esaote E" style={{ width: 38, height: 38, display: 'block' }} />
              </Box>
              <Typography variant="h5" fontWeight={700} color="primary" sx={{ flex: 1 }}>
                DICOM & Metadata Processing
              </Typography>
              <Box>
                {status==='waiting' && <Alert icon={false} severity="info" sx={{fontWeight:600, px:3, py:1, borderRadius:2}}>⏳ Waiting for result…</Alert>}
                {status==='error' && <Alert icon={false} severity="error" sx={{fontWeight:600, px:3, py:1, borderRadius:2}}>Error</Alert>}
                {status==='done' && <Alert icon={false} severity="success" sx={{fontWeight:600, px:3, py:1, borderRadius:2}}>Completed</Alert>}
              </Box>
            </Box>
            <Divider sx={{mb:4}}/>
            <Grid container spacing={{ xs: 2, md: 3 }} alignItems="flex-start" justifyContent="center">
              <Grid item xs={12} md={5} lg={5} xl={4} sx={{ display: 'flex', flexDirection: 'column', justifyContent: 'center' }}>
                <Box sx={{mb:3}}>
                  <Typography variant="subtitle1" color="primary" fontWeight={600} gutterBottom>
                    Image parameters
                  </Typography>
                  <TextField label="Study ID" value={studyId} onChange={e=>setStudyId(e.target.value)} fullWidth margin="dense" size="small" sx={{mb:1}}/>
                  <TextField label="Series ID" value={seriesId} onChange={e=>setSeriesId(e.target.value)} fullWidth margin="dense" size="small" sx={{mb:1}}/>
                  <TextField label="Image ID" value={imageId} onChange={e=>setImageId(e.target.value)} fullWidth margin="dense" size="small" sx={{mb:1}}/>
                  <TextField label="Scope" value={scope} onChange={e=>setScope(e.target.value)} fullWidth margin="dense" size="small" sx={{mb:2}}/>
                  <Typography variant="subtitle2" color="primary" fontWeight={500} sx={{mt:2}}>Algorithm:</Typography>
                  <Select value={algorithm} onChange={e=>setAlgorithm(e.target.value)} fullWidth size="small" sx={{ mb: 2 }}>
                    {algorithms.length === 0 && <MenuItem value="" disabled>No ACTIVE algorithms</MenuItem>}
                    {algorithms.map(algo => (
                      <MenuItem key={algo.algorithm_id} value={algo.algorithm_id}>
                        {algo.algorithm_id}
                      </MenuItem>
                    ))}
                  </Select>
                  <Button variant="contained" color="secondary" fullWidth onClick={startJob} sx={{ mb: 2, color: '#fff', fontWeight: 700, fontSize:18, py:1.5 }} disabled={status==='waiting' || !clientId}>Start processing</Button>
                  {!clientId && (
                    <Alert severity="warning" sx={{ mb: 2, fontWeight:600, fontSize:15, borderRadius:2 }}>
                      Provisioning client... Attendere
                    </Alert>
                  )}
                  {wsError && (
                    <Alert severity="error" sx={{ mb: 2, fontWeight:600, fontSize:15, borderRadius:2 }}>
                      Real-time non disponibile, ricarica la pagina o riprova più tardi.
                    </Alert>
                  )}
                </Box>
              </Grid>
              <Grid item xs={12} md={7} lg={7} xl={8}>
                {(status === 'waiting' || status === 'done') && (
                  <Grid container spacing={{ xs: 2, md: 3 }} wrap="nowrap" sx={{
                    flexWrap: { xs: 'wrap', md: 'nowrap' },
                    justifyContent: 'center',
                  }}>
                    <Grid item xs={12} md={6} sx={{ minWidth: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', px: { xs: 0, md: 1 } }}>
                      <Box sx={{
                        borderRadius: 3,
                        boxShadow: '0 2px 12px #e3061320',
                        bgcolor: '#fff',
                        p: 0,
                        mb: 2,
                        width: { xs: '100%', sm: 340, md: 420, lg: 440 },
                        maxWidth: '100%',
                        minWidth: 0,
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        overflow: 'hidden',
                      }}>
                        <Typography variant="subtitle1" color="primary" fontWeight={600} gutterBottom sx={{ width: '100%', p: 2, pb: 1 }}>
                          Original DICOM
                        </Typography>
                        <Box sx={{ width: '100%', display: 'flex', justifyContent: 'center', bgcolor: '#000', p: 0, m: 0 }}>
                          {originalUrl ? (
                            <DicomViewer url={originalUrl} />
                          ) : (
                            <Box sx={{ color: 'grey.500', mt: 2 }}>Loading original…</Box>
                          )}
                        </Box>
                        {originalMeta && (
                          <Box sx={{ width: '100%', mt: 0, p: 2, pt: 2, bgcolor: '#fafbfc', borderTop: '1px solid #eee', overflowX: 'auto', display: 'block' }}>
                        <DicomMetaCard title="Original Metadata" meta={originalMeta} tableProps={{
                              sx: {
                                width: '100%',
                                minWidth: 320,
                                tableLayout: 'fixed',
                                wordBreak: 'break-all',
                                whiteSpace: 'pre-line',
                                fontSize: '0.85em',
                                background: 'transparent',
                              },
                              'td': {
                                wordBreak: 'break-all',
                                whiteSpace: 'pre-line',
                                overflowWrap: 'break-word',
                                hyphens: 'auto',
                                fontSize: '0.85em',
                              },
                              'th': {
                                wordBreak: 'break-all',
                                whiteSpace: 'pre-line',
                                overflowWrap: 'break-word',
                                hyphens: 'auto',
                                fontSize: '0.85em',
                              }
                            }} />
                          </Box>
                        )}
                      </Box>
                    </Grid>
                    <Grid item xs={12} md={6} sx={{ minWidth: 0, display: 'flex', flexDirection: 'column', alignItems: 'center', px: { xs: 0, md: 1 } }}>
                      <Box sx={{
                        borderRadius: 3,
                        boxShadow: '0 2px 16px #4bb54330',
                        bgcolor: '#f8fff8',
                        p: 0,
                        mb: 2,
                        width: { xs: '100%', sm: 340, md: 420, lg: 440 },
                        maxWidth: '100%',
                        minWidth: 0,
                        display: 'flex',
                        flexDirection: 'column',
                        alignItems: 'center',
                        border: 'none',
                        transition: 'border 0.3s',
                        overflow: 'hidden',
                      }}>
                        <Typography variant="subtitle1" color="success.main" fontWeight={700} gutterBottom sx={{ width: '100%', p: 2, pb: 1 }}>
                          Processed DICOM
                        </Typography>
                        <Box sx={{ width: '100%', display: 'flex', justifyContent: 'center', bgcolor: '#000', p: 0, m: 0 }}>
                          {result && result.dicom?.url ? (
                            <DicomViewer url={result.dicom.url} />
                          ) : (
                            <Box sx={{ color: 'grey.500', mt: 2 }}>No result available yet.</Box>
                          )}
                        </Box>
                        {processedMeta && (
                          <Box sx={{ width: '100%', mt: 0, p: 2, pt: 2, bgcolor: '#f6fff6', borderTop: '1px solid #d0f5d0', overflowX: 'auto', display: 'block' }}>
                        <DicomMetaCard title="Processed Metadata" meta={processedMeta} compareTo={originalMeta} tableProps={{
                              sx: {
                                width: '100%',
                                minWidth: 320,
                                tableLayout: 'fixed',
                                wordBreak: 'break-all',
                                whiteSpace: 'pre-line',
                                fontSize: '0.85em',
                                background: 'transparent',
                              },
                              'td': {
                                wordBreak: 'break-all',
                                whiteSpace: 'pre-line',
                                overflowWrap: 'break-word',
                                hyphens: 'auto',
                                fontSize: '0.85em',
                              },
                              'th': {
                                wordBreak: 'break-all',
                                whiteSpace: 'pre-line',
                                overflowWrap: 'break-word',
                                hyphens: 'auto',
                                fontSize: '0.85em',
                              }
                            }} />
                          </Box>
                        )}
                      </Box>
                    </Grid>
                  </Grid>
                )}
              </Grid>
            </Grid>
          </CardContent>
        </Card>
      </Box>
    </ThemeProvider>
  );
}

const root = createRoot(document.getElementById('root'));
root.render(<App/>);
