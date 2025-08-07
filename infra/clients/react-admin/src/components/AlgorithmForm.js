import React, { useState, useEffect } from 'react';
import {
  Box,
  TextField,
  Button,
  Grid,
  Typography,
  Alert,
  CircularProgress,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Switch,
  FormControlLabel,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Chip,
  IconButton
} from '@mui/material';
import {
  ExpandMore as ExpandMoreIcon,
  Add as AddIcon,
  Delete as DeleteIcon
} from '@mui/icons-material';

const AlgorithmForm = ({ algorithm, onSave, onCancel }) => {
  const [formData, setFormData] = useState({
    algo_id: '',
    image_uri: '',
    cpu: 1024,
    memory: 2048,
    desired_count: 1,
    command: ['/app/worker.sh'],
    env: {},
    ...algorithm
  });
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [validationErrors, setValidationErrors] = useState({});
  const [envVars, setEnvVars] = useState([]);

  useEffect(() => {
    if (algorithm) {
      // Convert env object to array for editing
      const envArray = Object.entries(algorithm.env || {}).map(([key, value]) => ({ key, value }));
      setEnvVars(envArray);
      
      setFormData({
        algo_id: algorithm.algorithm_id || '', // Map from backend field
        image_uri: algorithm.image_uri || '',
        cpu: algorithm.cpu || 1024,
        memory: algorithm.memory || 2048,
        desired_count: algorithm.desired_count || 1,
        command: algorithm.command || ['/app/worker.sh'],
        env: algorithm.env || {}
      });
    } else {
      setEnvVars([]);
      setFormData({
        algo_id: '',
        image_uri: '',
        cpu: 1024,
        memory: 2048,
        desired_count: 1,
        command: ['/app/worker.sh'],
        env: {}
      });
    }
  }, [algorithm]);

  const validateForm = () => {
    const errors = {};
    
    if (!formData.algo_id?.trim()) {
      errors.algo_id = 'L\'ID algoritmo è obbligatorio';
    } else if (!/^[a-z0-9_][a-z0-9_\-]{2,63}$/.test(formData.algo_id)) {
      errors.algo_id = 'ID algoritmo non valido: usare [a-z0-9_-], 3-64 caratteri';
    }
    
    if (!formData.image_uri?.trim()) {
      errors.image_uri = 'L\'URI dell\'immagine è obbligatorio';
    }
    
    if (!formData.cpu || isNaN(formData.cpu) || parseInt(formData.cpu) <= 0) {
      errors.cpu = 'CPU deve essere un numero positivo';
    }
    
    if (!formData.memory || isNaN(formData.memory) || parseInt(formData.memory) <= 0) {
      errors.memory = 'Memoria deve essere un numero positivo';
    }

    if (!formData.desired_count || isNaN(formData.desired_count) || parseInt(formData.desired_count) < 0) {
      errors.desired_count = 'Il numero di istanze deve essere >= 0';
    }

    setValidationErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!validateForm()) {
      return;
    }
    
    setLoading(true);
    setError(null);
    
    try {
      // Convert envVars array back to object
      const envObject = {};
      envVars.forEach(envVar => {
        if (envVar.key && envVar.value) {
          envObject[envVar.key] = envVar.value;
        }
      });

      // Prepare data for API - exactly what the backend expects
      const algorithmData = {
        algo_id: formData.algo_id.trim(),
        image_uri: formData.image_uri.trim(),
        cpu: parseInt(formData.cpu),
        memory: parseInt(formData.memory),
        desired_count: parseInt(formData.desired_count),
        command: Array.isArray(formData.command) ? formData.command : [formData.command || '/app/worker.sh'],
        env: envObject
      };
      
      await onSave(algorithmData);
    } catch (err) {
      console.error('Form save error:', err);
      
      // Handle specific error cases
      if (err.status === 409) {
        // Algorithm already exists - show detailed error
        setError(err.message);
      } else {
        // Generic error
        setError(err.message || 'Errore durante il salvataggio');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }));
    
    // Clear validation error for this field
    if (validationErrors[field]) {
      setValidationErrors(prev => ({
        ...prev,
        [field]: undefined
      }));
    }
  };

  return (
    <Box component="form" onSubmit={handleSubmit} sx={{ mt: 2 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2, whiteSpace: 'pre-line' }}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Basic Information */}
        <Grid item xs={12}>
          <Typography variant="h6" gutterBottom>
            Informazioni Base
          </Typography>
        </Grid>
        
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="ID Algoritmo"
            value={formData.algo_id}
            onChange={(e) => handleInputChange('algo_id', e.target.value)}
            error={!!validationErrors.algo_id}
            helperText={validationErrors.algo_id || (algorithm ? 'L\'ID non può essere modificato' : 'Solo lettere minuscole, numeri, _ e -')}
            required
            disabled={!!algorithm} // Disable editing if updating existing algorithm
          />
        </Grid>
        
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Istanze Desiderate"
            type="number"
            value={formData.desired_count}
            onChange={(e) => handleInputChange('desired_count', e.target.value)}
            error={!!validationErrors.desired_count}
            helperText={validationErrors.desired_count || 'Numero di istanze da eseguire'}
            inputProps={{ min: 0 }}
            required
          />
        </Grid>
        
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="URI Immagine Docker"
            value={formData.image_uri}
            onChange={(e) => handleInputChange('image_uri', e.target.value)}
            error={!!validationErrors.image_uri}
            helperText={validationErrors.image_uri || 'Es: 123456789.dkr.ecr.eu-central-1.amazonaws.com/my-algo:latest'}
            required
          />
        </Grid>

        {/* Resource Configuration */}
        <Grid item xs={12}>
          <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
            Configurazione Risorse
          </Typography>
        </Grid>
        
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="CPU (unità)"
            type="number"
            value={formData.cpu}
            onChange={(e) => handleInputChange('cpu', e.target.value)}
            error={!!validationErrors.cpu}
            helperText={validationErrors.cpu || 'CPU in unità (es: 1024 = 1 vCPU)'}
            inputProps={{ min: 256, step: 256 }}
            required
          />
        </Grid>
        
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Memoria (MB)"
            type="number"
            value={formData.memory}
            onChange={(e) => handleInputChange('memory', e.target.value)}
            error={!!validationErrors.memory}
            helperText={validationErrors.memory || 'Memoria in MB'}
            inputProps={{ min: 512, step: 512 }}
            required
          />
        </Grid>
        {/* Command Configuration */}
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Comando di Avvio"
            value={Array.isArray(formData.command) ? formData.command.join(' ') : formData.command}
            onChange={(e) => handleInputChange('command', e.target.value.split(' ').filter(cmd => cmd.trim()))}
            helperText="Comando per avviare l'algoritmo (default: /app/worker.sh)"
          />
        </Grid>

        {/* Advanced Configuration */}
        <Grid item xs={12}>
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Variabili di Ambiente</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                    <Typography variant="subtitle1">Variabili di Ambiente Personalizzate</Typography>
                    <Button
                      size="small"
                      startIcon={<AddIcon />}
                      onClick={() => setEnvVars([...envVars, { key: '', value: '' }])}
                    >
                      Aggiungi
                    </Button>
                  </Box>
                  {envVars.map((env, index) => (
                    <Grid container spacing={1} key={index} sx={{ mb: 1 }}>
                      <Grid item xs={5}>
                        <TextField
                          fullWidth
                          size="small"
                          label="Chiave"
                          value={env.key}
                          onChange={(e) => {
                            const newEnvVars = [...envVars];
                            newEnvVars[index] = { ...newEnvVars[index], key: e.target.value };
                            setEnvVars(newEnvVars);
                          }}
                        />
                      </Grid>
                      <Grid item xs={6}>
                        <TextField
                          fullWidth
                          size="small"
                          label="Valore"
                          value={env.value}
                          onChange={(e) => {
                            const newEnvVars = [...envVars];
                            newEnvVars[index] = { ...newEnvVars[index], value: e.target.value };
                            setEnvVars(newEnvVars);
                          }}
                        />
                      </Grid>
                      <Grid item xs={1}>
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => setEnvVars(envVars.filter((_, i) => i !== index))}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </Grid>
                    </Grid>
                  ))}
                </Grid>
              </Grid>
            </AccordionDetails>
          </Accordion>
        </Grid>
      </Grid>

      <Box display="flex" justifyContent="flex-end" gap={2} sx={{ mt: 3 }}>
        <Button
          variant="outlined"
          onClick={onCancel}
          disabled={loading}
        >
          Annulla
        </Button>
        <Button
          type="submit"
          variant="contained"
          disabled={loading}
          startIcon={loading ? <CircularProgress size={16} /> : null}
        >
          {loading ? 'Salvando...' : (algorithm ? 'Aggiorna' : 'Crea')}
        </Button>
      </Box>
    </Box>
  );
};

export default AlgorithmForm;
