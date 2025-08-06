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
    name: '',
    description: '',
    version: '1.0.0',
    image: '',
    cpu: '512',
    memory: '1024',
    enabled: true,
    environment: [],
    ports: [],
    volumes: [],
    commands: [],
    ...algorithm
  });
  
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [validationErrors, setValidationErrors] = useState({});

  useEffect(() => {
    if (algorithm) {
      setFormData({
        name: '',
        description: '',
        version: '1.0.0',
        image: '',
        cpu: '512',
        memory: '1024',
        enabled: true,
        environment: [],
        ports: [],
        volumes: [],
        commands: [],
        ...algorithm
      });
    }
  }, [algorithm]);

  const validateForm = () => {
    const errors = {};
    
    if (!formData.name?.trim()) {
      errors.name = 'Il nome è obbligatorio';
    }
    
    if (!formData.image?.trim()) {
      errors.image = 'L\'immagine Docker è obbligatoria';
    }
    
    if (!formData.version?.trim()) {
      errors.version = 'La versione è obbligatoria';
    }
    
    if (!formData.cpu || isNaN(formData.cpu) || parseInt(formData.cpu) <= 0) {
      errors.cpu = 'CPU deve essere un numero positivo';
    }
    
    if (!formData.memory || isNaN(formData.memory) || parseInt(formData.memory) <= 0) {
      errors.memory = 'Memoria deve essere un numero positivo';
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
      // Prepare data for API
      const algorithmData = {
        ...formData,
        cpu: parseInt(formData.cpu),
        memory: parseInt(formData.memory),
        environment: formData.environment.filter(env => env.key && env.value),
        ports: formData.ports.filter(port => port.containerPort),
        volumes: formData.volumes.filter(vol => vol.name && vol.mountPath),
        commands: formData.commands.filter(cmd => cmd.trim())
      };
      
      await onSave(algorithmData);
    } catch (err) {
      setError(err.message);
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

  const handleArrayAdd = (field, defaultItem) => {
    setFormData(prev => ({
      ...prev,
      [field]: [...prev[field], defaultItem]
    }));
  };

  const handleArrayRemove = (field, index) => {
    setFormData(prev => ({
      ...prev,
      [field]: prev[field].filter((_, i) => i !== index)
    }));
  };

  const handleArrayItemChange = (field, index, key, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: prev[field].map((item, i) => 
        i === index ? { ...item, [key]: value } : item
      )
    }));
  };

  const handleCommandChange = (index, value) => {
    setFormData(prev => ({
      ...prev,
      commands: prev.commands.map((cmd, i) => i === index ? value : cmd)
    }));
  };

  return (
    <Box component="form" onSubmit={handleSubmit} sx={{ mt: 2 }}>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }}>
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
            label="Nome Algoritmo"
            value={formData.name}
            onChange={(e) => handleInputChange('name', e.target.value)}
            error={!!validationErrors.name}
            helperText={validationErrors.name}
            required
          />
        </Grid>
        
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Versione"
            value={formData.version}
            onChange={(e) => handleInputChange('version', e.target.value)}
            error={!!validationErrors.version}
            helperText={validationErrors.version}
            required
          />
        </Grid>
        
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Descrizione"
            multiline
            rows={3}
            value={formData.description}
            onChange={(e) => handleInputChange('description', e.target.value)}
          />
        </Grid>
        
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Immagine Docker"
            value={formData.image}
            onChange={(e) => handleInputChange('image', e.target.value)}
            error={!!validationErrors.image}
            helperText={validationErrors.image || 'Es: my-registry/algorithm:latest'}
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
            label="CPU (vCPU)"
            type="number"
            value={formData.cpu}
            onChange={(e) => handleInputChange('cpu', e.target.value)}
            error={!!validationErrors.cpu}
            helperText={validationErrors.cpu || 'CPU in unità vCPU (es: 512 = 0.5 vCPU)'}
            inputProps={{ min: 1 }}
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
            inputProps={{ min: 1 }}
            required
          />
        </Grid>
        
        <Grid item xs={12}>
          <FormControlLabel
            control={
              <Switch
                checked={formData.enabled}
                onChange={(e) => handleInputChange('enabled', e.target.checked)}
              />
            }
            label="Algoritmo abilitato"
          />
        </Grid>

        {/* Advanced Configuration */}
        <Grid item xs={12}>
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Configurazione Avanzata</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={2}>
                {/* Environment Variables */}
                <Grid item xs={12}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                    <Typography variant="subtitle1">Variabili di Ambiente</Typography>
                    <Button
                      size="small"
                      startIcon={<AddIcon />}
                      onClick={() => handleArrayAdd('environment', { key: '', value: '' })}
                    >
                      Aggiungi
                    </Button>
                  </Box>
                  {formData.environment.map((env, index) => (
                    <Grid container spacing={1} key={index} sx={{ mb: 1 }}>
                      <Grid item xs={5}>
                        <TextField
                          fullWidth
                          size="small"
                          label="Chiave"
                          value={env.key}
                          onChange={(e) => handleArrayItemChange('environment', index, 'key', e.target.value)}
                        />
                      </Grid>
                      <Grid item xs={6}>
                        <TextField
                          fullWidth
                          size="small"
                          label="Valore"
                          value={env.value}
                          onChange={(e) => handleArrayItemChange('environment', index, 'value', e.target.value)}
                        />
                      </Grid>
                      <Grid item xs={1}>
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => handleArrayRemove('environment', index)}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </Grid>
                    </Grid>
                  ))}
                </Grid>

                {/* Commands */}
                <Grid item xs={12}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                    <Typography variant="subtitle1">Comandi di Avvio</Typography>
                    <Button
                      size="small"
                      startIcon={<AddIcon />}
                      onClick={() => handleArrayAdd('commands', '')}
                    >
                      Aggiungi
                    </Button>
                  </Box>
                  {formData.commands.map((command, index) => (
                    <Grid container spacing={1} key={index} sx={{ mb: 1 }}>
                      <Grid item xs={11}>
                        <TextField
                          fullWidth
                          size="small"
                          label={`Comando ${index + 1}`}
                          value={command}
                          onChange={(e) => handleCommandChange(index, e.target.value)}
                        />
                      </Grid>
                      <Grid item xs={1}>
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => handleArrayRemove('commands', index)}
                        >
                          <DeleteIcon />
                        </IconButton>
                      </Grid>
                    </Grid>
                  ))}
                </Grid>

                {/* Ports */}
                <Grid item xs={12}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                    <Typography variant="subtitle1">Porte</Typography>
                    <Button
                      size="small"
                      startIcon={<AddIcon />}
                      onClick={() => handleArrayAdd('ports', { containerPort: '', protocol: 'TCP' })}
                    >
                      Aggiungi
                    </Button>
                  </Box>
                  {formData.ports.map((port, index) => (
                    <Grid container spacing={1} key={index} sx={{ mb: 1 }}>
                      <Grid item xs={5}>
                        <TextField
                          fullWidth
                          size="small"
                          type="number"
                          label="Porta Container"
                          value={port.containerPort}
                          onChange={(e) => handleArrayItemChange('ports', index, 'containerPort', e.target.value)}
                          inputProps={{ min: 1, max: 65535 }}
                        />
                      </Grid>
                      <Grid item xs={6}>
                        <FormControl fullWidth size="small">
                          <InputLabel>Protocollo</InputLabel>
                          <Select
                            value={port.protocol || 'TCP'}
                            onChange={(e) => handleArrayItemChange('ports', index, 'protocol', e.target.value)}
                          >
                            <MenuItem value="TCP">TCP</MenuItem>
                            <MenuItem value="UDP">UDP</MenuItem>
                          </Select>
                        </FormControl>
                      </Grid>
                      <Grid item xs={1}>
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => handleArrayRemove('ports', index)}
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
