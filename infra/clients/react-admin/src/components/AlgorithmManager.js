import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Grid,
  Card,
  CardContent,
  CardActions,
  Chip,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Alert,
  CircularProgress,
  Fab,
  Tooltip
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  Refresh as RefreshIcon
} from '@mui/icons-material';
import { getCurrentUser } from 'aws-amplify/auth';

import AlgorithmForm from './AlgorithmForm';
import apiService from '../services/apiService';

const AlgorithmManager = () => {
  const [algorithms, setAlgorithms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [formOpen, setFormOpen] = useState(false);
  const [selectedAlgorithm, setSelectedAlgorithm] = useState(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [algorithmToDelete, setAlgorithmToDelete] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    loadAlgorithms();
  }, []);

  const loadAlgorithms = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // The apiService will automatically get the token from Amplify
      const response = await apiService.getAlgorithms();
      setAlgorithms(response.algorithms || []);
    } catch (err) {
      console.error('Error loading algorithms:', err);
      setError('Errore nel caricamento degli algoritmi: ' + (err.message || 'Errore sconosciuto'));
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadAlgorithms();
    setRefreshing(false);
  };

  const handleCreateAlgorithm = () => {
    setSelectedAlgorithm(null);
    setFormOpen(true);
  };

  const handleEditAlgorithm = (algorithm) => {
    setSelectedAlgorithm(algorithm);
    setFormOpen(true);
  };

  const handleDeleteAlgorithm = (algorithm) => {
    setAlgorithmToDelete(algorithm);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!algorithmToDelete) return;
    
    try {
      await apiService.deleteAlgorithm(algorithmToDelete.id);
      
      // Remove from local state
      setAlgorithms(prev => prev.filter(a => a.id !== algorithmToDelete.id));
      setDeleteDialogOpen(false);
      setAlgorithmToDelete(null);
    } catch (err) {
      console.error('Error deleting algorithm:', err);
      setError('Errore nell\'eliminazione dell\'algoritmo: ' + (err.message || 'Errore sconosciuto'));
    }
  };

  const handleFormSave = async (algorithmData) => {
    try {
      if (selectedAlgorithm) {
        // Update existing algorithm
        const updated = await apiService.updateAlgorithm(selectedAlgorithm.id, algorithmData);
        setAlgorithms(prev => prev.map(a => a.id === selectedAlgorithm.id ? updated : a));
      } else {
        // Create new algorithm
        const created = await apiService.createAlgorithm(algorithmData);
        setAlgorithms(prev => [...prev, created]);
      }
      
      setFormOpen(false);
      setSelectedAlgorithm(null);
    } catch (err) {
      console.error('Error saving algorithm:', err);
      throw new Error('Errore nel salvataggio dell\'algoritmo: ' + (err.message || 'Errore sconosciuto'));
    }
  };

  const getStatusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'active':
      case 'running':
        return 'success';
      case 'inactive':
      case 'stopped':
        return 'error';
      case 'pending':
      case 'starting':
        return 'warning';
      default:
        return 'default';
    }
  };

  const getStatusLabel = (status) => {
    switch (status?.toLowerCase()) {
      case 'active':
        return 'Attivo';
      case 'inactive':
        return 'Inattivo';
      case 'pending':
        return 'In attesa';
      case 'running':
        return 'In esecuzione';
      case 'stopped':
        return 'Fermato';
      default:
        return status || 'Sconosciuto';
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
        <Typography variant="body1" sx={{ ml: 2 }}>
          Caricamento algoritmi...
        </Typography>
      </Box>
    );
  }

  return (
    <Box>
      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" component="h2">
          Algoritmi di Elaborazione
        </Typography>
        <Box>
          <Tooltip title="Aggiorna lista">
            <Button
              variant="outlined"
              startIcon={refreshing ? <CircularProgress size={16} /> : <RefreshIcon />}
              onClick={handleRefresh}
              disabled={refreshing}
              sx={{ mr: 1 }}
            >
              Aggiorna
            </Button>
          </Tooltip>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleCreateAlgorithm}
          >
            Nuovo Algoritmo
          </Button>
        </Box>
      </Box>

      {algorithms.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            Nessun algoritmo configurato
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            Inizia creando il tuo primo algoritmo di elaborazione immagini
          </Typography>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleCreateAlgorithm}
          >
            Crea Primo Algoritmo
          </Button>
        </Paper>
      ) : (
        <Grid container spacing={3}>
          {algorithms.map((algorithm) => (
            <Grid item xs={12} md={6} lg={4} key={algorithm.id}>
              <Card className="algorithm-card" sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <CardContent sx={{ flexGrow: 1 }}>
                  <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
                    <Typography variant="h6" component="h3" noWrap>
                      {algorithm.name}
                    </Typography>
                    <Chip
                      label={getStatusLabel(algorithm.status)}
                      color={getStatusColor(algorithm.status)}
                      size="small"
                      className="status-chip"
                    />
                  </Box>
                  
                  <Typography variant="body2" color="text.secondary" paragraph>
                    {algorithm.description || 'Nessuna descrizione disponibile'}
                  </Typography>
                  
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="caption" display="block" color="text.secondary">
                      <strong>Versione:</strong> {algorithm.version || 'N/A'}
                    </Typography>
                    <Typography variant="caption" display="block" color="text.secondary">
                      <strong>CPU:</strong> {algorithm.cpu || 'N/A'} | <strong>Memoria:</strong> {algorithm.memory || 'N/A'}
                    </Typography>
                    {algorithm.image && (
                      <Typography variant="caption" display="block" color="text.secondary" noWrap>
                        <strong>Immagine:</strong> {algorithm.image}
                      </Typography>
                    )}
                  </Box>
                </CardContent>
                
                <CardActions>
                  <Button
                    size="small"
                    startIcon={<EditIcon />}
                    onClick={() => handleEditAlgorithm(algorithm)}
                  >
                    Modifica
                  </Button>
                  <Button
                    size="small"
                    color="error"
                    startIcon={<DeleteIcon />}
                    onClick={() => handleDeleteAlgorithm(algorithm)}
                  >
                    Elimina
                  </Button>
                </CardActions>
              </Card>
            </Grid>
          ))}
        </Grid>
      )}

      {/* Algorithm Form Dialog */}
      <Dialog
        open={formOpen}
        onClose={() => setFormOpen(false)}
        maxWidth="md"
        fullWidth
      >
        <DialogTitle>
          {selectedAlgorithm ? 'Modifica Algoritmo' : 'Nuovo Algoritmo'}
        </DialogTitle>
        <DialogContent>
          <AlgorithmForm
            algorithm={selectedAlgorithm}
            onSave={handleFormSave}
            onCancel={() => setFormOpen(false)}
          />
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog
        open={deleteDialogOpen}
        onClose={() => setDeleteDialogOpen(false)}
      >
        <DialogTitle>Conferma Eliminazione</DialogTitle>
        <DialogContent>
          <Typography>
            Sei sicuro di voler eliminare l'algoritmo "{algorithmToDelete?.name}"?
            Questa operazione non può essere annullata.
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>
            Annulla
          </Button>
          <Button onClick={confirmDelete} color="error" variant="contained">
            Elimina
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AlgorithmManager;
