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
      setAlgorithms(response.items || []); // Backend returns { items: [...] }
    } catch (err) {
      console.error('Error loading algorithms:', err);
      setError('Error loading algorithms: ' + (err.message || 'Unknown error'));
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

  const confirmDelete = async (hard = false) => {
    if (!algorithmToDelete) return;
    
    try {
      await apiService.deleteAlgorithm(algorithmToDelete.algorithm_id, hard);
      
      // Remove from local state
      setAlgorithms(prev => prev.filter(a => a.algorithm_id !== algorithmToDelete.algorithm_id));
      setDeleteDialogOpen(false);
      setAlgorithmToDelete(null);
    } catch (err) {
      console.error('Error deleting algorithm:', err);
      setError('Error deleting algorithm: ' + (err.message || 'Unknown error'));
    }
  };

  const handleFormSave = async (algorithmData) => {
    try {
      if (selectedAlgorithm) {
        // Update existing algorithm using PATCH
        const updated = await apiService.updateAlgorithm(selectedAlgorithm.algorithm_id, algorithmData);
        setAlgorithms(prev => prev.map(a => a.algorithm_id === selectedAlgorithm.algorithm_id ? { ...a, ...algorithmData } : a));
      } else {
        // Create new algorithm using POST
        const created = await apiService.createAlgorithm(algorithmData);
        // Add the new algorithm to the list with the response data
        setAlgorithms(prev => [...prev, { ...algorithmData, status: 'REGISTERED' }]);
      }
      
      setFormOpen(false);
      setSelectedAlgorithm(null);
      
      // Reload algorithms to get updated status
      setTimeout(() => {
        loadAlgorithms();
      }, 1000);
    } catch (err) {
      console.error('Error saving algorithm:', err);
      throw new Error('Error saving algorithm: ' + (err.message || 'Unknown error'));
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
        return 'Active';
      case 'inactive':
        return 'Inactive';
      case 'pending':
        return 'Pending';
      case 'running':
        return 'Running';
      case 'stopped':
        return 'Stopped';
      default:
        return status || 'Unknown';
    }
  };

  if (loading) {
    return (
      <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
        <CircularProgress />
        <Typography variant="body1" sx={{ ml: 2 }}>
          Loading algorithms...
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
          Processing Algorithms
        </Typography>
        <Box>
          <Tooltip title="Refresh list">
            <Button
              variant="outlined"
              startIcon={refreshing ? <CircularProgress size={16} /> : <RefreshIcon />}
              onClick={handleRefresh}
              disabled={refreshing}
              sx={{ mr: 1 }}
            >
              Refresh
            </Button>
          </Tooltip>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleCreateAlgorithm}
          >
            New Algorithm
          </Button>
        </Box>
      </Box>

      {algorithms.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            No algorithms configured
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            Start by creating your first image processing algorithm
          </Typography>
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleCreateAlgorithm}
          >
            Create First Algorithm
          </Button>
        </Paper>
      ) : (
        <Grid container spacing={3}>
          {algorithms.map((algorithm) => (
            <Grid item xs={12} md={6} lg={4} key={algorithm.algorithm_id}>
              <Card className="algorithm-card" sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
                <CardContent sx={{ flexGrow: 1 }}>
                  <Box display="flex" justifyContent="space-between" alignItems="flex-start" mb={2}>
                    <Typography variant="h6" component="h3" noWrap>
                      {algorithm.algorithm_id}
                    </Typography>
                    <Chip
                      label={getStatusLabel(algorithm.status)}
                      color={getStatusColor(algorithm.status)}
                      size="small"
                      className="status-chip"
                    />
                  </Box>
                  
                  <Typography variant="body2" color="text.secondary" paragraph>
                    URI: {algorithm.image_uri || 'Not specified'}
                  </Typography>
                  
                  <Box sx={{ mt: 2 }}>
                    <Typography variant="caption" display="block" color="text.secondary">
                      <strong>CPU:</strong> {algorithm.cpu || 'N/A'} | <strong>Memory:</strong> {algorithm.memory || 'N/A'} MB
                    </Typography>
                    <Typography variant="caption" display="block" color="text.secondary">
                      <strong>Instances:</strong> {algorithm.desired_count || 1} | <strong>Command:</strong> {Array.isArray(algorithm.command) ? algorithm.command.join(' ') : algorithm.command || '/app/worker.sh'}
                    </Typography>
                    {algorithm.env && Object.keys(algorithm.env).length > 0 && (
                      <Typography variant="caption" display="block" color="text.secondary">
                        <strong>Env vars:</strong> {Object.keys(algorithm.env).length} configured
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
                    Edit
                  </Button>
                  <Button
                    size="small"
                    color="error"
                    startIcon={<DeleteIcon />}
                    onClick={() => handleDeleteAlgorithm(algorithm)}
                  >
                    Delete
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
          {selectedAlgorithm ? 'Edit Algorithm' : 'New Algorithm'}
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
        <DialogTitle>Confirm Deletion</DialogTitle>
        <DialogContent>
          <Typography paragraph>
            Are you sure you want to delete algorithm "{algorithmToDelete?.algorithm_id}"?
          </Typography>
          <Typography variant="body2" color="text.secondary">
            • <strong>Scale to zero:</strong> Stops the algorithm but keeps configuration<br/>
            • <strong>Delete completely:</strong> Removes everything (not reversible)
          </Typography>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDeleteDialogOpen(false)}>
            Cancel
          </Button>
          <Button onClick={() => confirmDelete(false)} color="warning" variant="outlined">
            Scale to Zero
          </Button>
          <Button onClick={() => confirmDelete(true)} color="error" variant="contained">
            Delete Completely
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
};

export default AlgorithmManager;
