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
      errors.algo_id = 'Algorithm ID is required';
    } else if (!/^[a-z0-9_][a-z0-9_\-]{2,63}$/.test(formData.algo_id)) {
      errors.algo_id = 'Invalid algorithm ID: use [a-z0-9_-], 3-64 characters';
    }
    
    if (!formData.image_uri?.trim()) {
      errors.image_uri = 'Image URI is required';
    }
    
    if (!formData.cpu || isNaN(formData.cpu) || parseInt(formData.cpu) <= 0) {
      errors.cpu = 'CPU must be a positive number';
    }
    
    if (!formData.memory || isNaN(formData.memory) || parseInt(formData.memory) <= 0) {
      errors.memory = 'Memory must be a positive number';
    }

    if (!formData.desired_count || isNaN(formData.desired_count) || parseInt(formData.desired_count) < 0) {
      errors.desired_count = 'Number of instances must be >= 0';
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
        setError(err.message || 'Error during save');
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
            Basic Information
          </Typography>
        </Grid>
        
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Algorithm ID"
            value={formData.algo_id}
            onChange={(e) => handleInputChange('algo_id', e.target.value)}
            error={!!validationErrors.algo_id}
            helperText={validationErrors.algo_id || (algorithm ? 'ID cannot be modified' : 'Only lowercase letters, numbers, _ and -')}
            required
            disabled={!!algorithm} // Disable editing if updating existing algorithm
          />
        </Grid>
        
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Desired Instances"
            type="number"
            value={formData.desired_count}
            onChange={(e) => handleInputChange('desired_count', e.target.value)}
            error={!!validationErrors.desired_count}
            helperText={validationErrors.desired_count || 'Number of instances to run'}
            inputProps={{ min: 0 }}
            required
          />
        </Grid>
        
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Docker Image URI"
            value={formData.image_uri}
            onChange={(e) => handleInputChange('image_uri', e.target.value)}
            error={!!validationErrors.image_uri}
            helperText={validationErrors.image_uri || 'Ex: 123456789.dkr.ecr.eu-central-1.amazonaws.com/my-algo:latest'}
            required
          />
        </Grid>

        {/* Resource Configuration */}
        <Grid item xs={12}>
          <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
            Resource Configuration
          </Typography>
        </Grid>
        
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="CPU (units)"
            type="number"
            value={formData.cpu}
            onChange={(e) => handleInputChange('cpu', e.target.value)}
            error={!!validationErrors.cpu}
            helperText={validationErrors.cpu || 'CPU in units (ex: 1024 = 1 vCPU)'}
            inputProps={{ min: 256, step: 256 }}
            required
          />
        </Grid>
        
        <Grid item xs={12} sm={6}>
          <TextField
            fullWidth
            label="Memory (MB)"
            type="number"
            value={formData.memory}
            onChange={(e) => handleInputChange('memory', e.target.value)}
            error={!!validationErrors.memory}
            helperText={validationErrors.memory || 'Memory in MB'}
            inputProps={{ min: 512, step: 512 }}
            required
          />
        </Grid>
        {/* Command Configuration */}
        <Grid item xs={12}>
          <TextField
            fullWidth
            label="Startup Command"
            value={Array.isArray(formData.command) ? formData.command.join(' ') : formData.command}
            onChange={(e) => handleInputChange('command', e.target.value.split(' ').filter(cmd => cmd.trim()))}
            helperText="Command to start the algorithm (default: /app/worker.sh)"
          />
        </Grid>

        {/* Advanced Configuration */}
        <Grid item xs={12}>
          <Accordion>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Typography variant="h6">Environment Variables</Typography>
            </AccordionSummary>
            <AccordionDetails>
              <Grid container spacing={2}>
                <Grid item xs={12}>
                  <Box display="flex" justifyContent="space-between" alignItems="center" mb={2}>
                    <Typography variant="subtitle1">Custom Environment Variables</Typography>
                    <Button
                      size="small"
                      startIcon={<AddIcon />}
                      onClick={() => setEnvVars([...envVars, { key: '', value: '' }])}
                    >
                      Add
                    </Button>
                  </Box>
                  {envVars.map((env, index) => (
                    <Grid container spacing={1} key={index} sx={{ mb: 1 }}>
                      <Grid item xs={5}>
                        <TextField
                          fullWidth
                          size="small"
                          label="Key"
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
                          label="Value"
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
          Cancel
        </Button>
        <Button
          type="submit"
          variant="contained"
          disabled={loading}
          startIcon={loading ? <CircularProgress size={16} /> : null}
        >
          {loading ? 'Saving...' : (algorithm ? 'Update' : 'Create')}
        </Button>
      </Box>
    </Box>
  );
};

export default AlgorithmForm;
