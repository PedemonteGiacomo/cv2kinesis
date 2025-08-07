import React, { useState, useEffect } from 'react';
import {
  Box,
  Paper,
  Typography,
  Button,
  Grid,
  Card,
  CardContent,
  Chip,
  Alert,
  CircularProgress,
  TextField,
  InputAdornment,
  Tooltip
} from '@mui/material';
import {
  Search as SearchIcon,
  Refresh as RefreshIcon,
} from '@mui/icons-material';

import apiService from '../services/apiService';

const AlgorithmViewer = () => {
  const [algorithms, setAlgorithms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshing, setRefreshing] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  useEffect(() => {
    loadAlgorithms();
  }, []);

  const loadAlgorithms = async () => {
    try {
      setLoading(true);
      setError(null);
      
      // Call public API endpoint (no authentication required)
      const response = await apiService.getAlgorithms();
      setAlgorithms(response.items || []);
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
      case 'registered':
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
      case 'registered':
        return 'Registrato';
      default:
        return status || 'Sconosciuto';
    }
  };

  const filteredAlgorithms = algorithms.filter(algorithm => {
    if (!searchTerm) return true;
    const term = searchTerm.toLowerCase();
    return (
      algorithm.algorithm_id?.toLowerCase().includes(term) ||
      algorithm.name?.toLowerCase().includes(term) ||
      algorithm.description?.toLowerCase().includes(term)
    );
  });

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

      {/* Public Access Notice */}
      <Paper sx={{ p: 2, mb: 3, bgcolor: 'success.light', color: 'success.contrastText' }}>
        <Typography variant="h6" gutterBottom>
          Catalogo Algoritmi Pubblico
        </Typography>
        <Typography variant="body2">
          Questa è la visualizzazione pubblica degli algoritmi disponibili. 
          Non è richiesta autenticazione per consultare questo catalogo.
        </Typography>
      </Paper>

      {/* Search and Refresh */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" component="h2">
          Algoritmi Disponibili
        </Typography>
        <Box display="flex" alignItems="center" gap={2}>
          <TextField
            size="small"
            placeholder="Cerca algoritmi..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            InputProps={{
              startAdornment: (
                <InputAdornment position="start">
                  <SearchIcon />
                </InputAdornment>
              ),
            }}
            sx={{ minWidth: 250 }}
          />
          <Tooltip title="Aggiorna lista">
            <Button
              variant="outlined"
              startIcon={refreshing ? <CircularProgress size={16} /> : <RefreshIcon />}
              onClick={handleRefresh}
              disabled={refreshing}
            >
              Aggiorna
            </Button>
          </Tooltip>
        </Box>
      </Box>

      {filteredAlgorithms.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            {searchTerm ? 'Nessun algoritmo trovato' : 'Nessun algoritmo disponibile'}
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            {searchTerm 
              ? 'Prova a modificare i termini di ricerca'
              : 'Gli algoritmi verranno mostrati qui una volta configurati'
            }
          </Typography>
        </Paper>
      ) : (
        <>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Trovati {filteredAlgorithms.length} algoritmi
          </Typography>
          
          <Grid container spacing={3}>
            {filteredAlgorithms.map((algorithm) => (
              <Grid item xs={12} md={6} lg={4} key={algorithm.algorithm_id}>
                <Card sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                  <CardContent sx={{ flexGrow: 1 }}>
                    <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
                      <Typography variant="h6" component="h3" noWrap>
                        {algorithm.name || algorithm.algorithm_id}
                      </Typography>
                      <Chip
                        label={getStatusLabel(algorithm.status)}
                        color={getStatusColor(algorithm.status)}
                        size="small"
                      />
                    </Box>
                    
                    <Typography variant="body2" color="text.secondary" paragraph>
                      {algorithm.description || 'Nessuna descrizione disponibile'}
                    </Typography>
                    
                    <Box sx={{ mt: 2 }}>
                      <Typography variant="caption" display="block" color="text.secondary">
                        <strong>ID:</strong> {algorithm.algorithm_id}
                      </Typography>
                      <Typography variant="caption" display="block" color="text.secondary">
                        <strong>CPU:</strong> {algorithm.cpu || 'N/A'} | <strong>Memoria:</strong> {algorithm.memory || 'N/A'}MB
                      </Typography>
                      <Typography variant="caption" display="block" color="text.secondary">
                        <strong>Istanze:</strong> {algorithm.desired_count || 'N/A'}
                      </Typography>
                      {algorithm.version && (
                        <Typography variant="caption" display="block" color="text.secondary">
                          <strong>Versione:</strong> {algorithm.version}
                        </Typography>
                      )}
                      {algorithm.category && (
                        <Typography variant="caption" display="block" color="text.secondary">
                          <strong>Categoria:</strong> {algorithm.category}
                        </Typography>
                      )}
                    </Box>
                    
                    {algorithm.tags && algorithm.tags.length > 0 && (
                      <Box sx={{ mt: 2 }}>
                        <Typography variant="caption" display="block" color="text.secondary" sx={{ mb: 1 }}>
                          <strong>Tags:</strong>
                        </Typography>
                        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.5 }}>
                          {algorithm.tags.slice(0, 3).map((tag, index) => (
                            <Chip key={index} label={tag} size="small" variant="outlined" />
                          ))}
                          {algorithm.tags.length > 3 && (
                            <Typography variant="caption" color="text.secondary">
                              +{algorithm.tags.length - 3} altri
                            </Typography>
                          )}
                        </Box>
                      </Box>
                    )}
                  </CardContent>
                </Card>
              </Grid>
            ))}
          </Grid>
        </>
      )}
    </Box>
  );
};

export default AlgorithmViewer;
