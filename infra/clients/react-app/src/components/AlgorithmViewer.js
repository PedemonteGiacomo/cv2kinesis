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
        return 'Active';
      case 'inactive':
        return 'Inactive';
      case 'pending':
        return 'Pending';
      case 'running':
        return 'Running';
      case 'stopped':
        return 'Stopped';
      case 'registered':
        return 'Registered';
      default:
        return status || 'Unknown';
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

      {/* Public Access Notice */}
      <Paper sx={{ p: 2, mb: 3, bgcolor: 'success.light', color: 'success.contrastText' }}>
        <Typography variant="h6" gutterBottom>
          Public Algorithm Catalog
        </Typography>
        <Typography variant="body2">
          This is the public view of available algorithms. 
          No authentication is required to view this catalog.
        </Typography>
      </Paper>

      {/* Search and Refresh */}
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h5" component="h2">
          Available Algorithms
        </Typography>
        <Box display="flex" alignItems="center" gap={2}>
          <TextField
            size="small"
            placeholder="Search algorithms..."
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
          <Tooltip title="Refresh list">
            <Button
              variant="outlined"
              startIcon={refreshing ? <CircularProgress size={16} /> : <RefreshIcon />}
              onClick={handleRefresh}
              disabled={refreshing}
            >
              Refresh
            </Button>
          </Tooltip>
        </Box>
      </Box>

      {filteredAlgorithms.length === 0 ? (
        <Paper sx={{ p: 4, textAlign: 'center' }}>
          <Typography variant="h6" color="text.secondary" gutterBottom>
            {searchTerm ? 'No algorithms found' : 'No algorithms available'}
          </Typography>
          <Typography variant="body2" color="text.secondary" paragraph>
            {searchTerm 
              ? 'Try modifying your search terms'
              : 'Algorithms will be displayed here once configured'
            }
          </Typography>
        </Paper>
      ) : (
        <>
          <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
            Found {filteredAlgorithms.length} algorithms
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
                      {algorithm.description || 'No description available'}
                    </Typography>
                    
                    <Box sx={{ mt: 2 }}>
                      <Typography variant="caption" display="block" color="text.secondary">
                        <strong>ID:</strong> {algorithm.algorithm_id}
                      </Typography>
                      <Typography variant="caption" display="block" color="text.secondary">
                        <strong>CPU:</strong> {algorithm.cpu || 'N/A'} | <strong>Memory:</strong> {algorithm.memory || 'N/A'}MB
                      </Typography>
                      <Typography variant="caption" display="block" color="text.secondary">
                        <strong>Instances:</strong> {algorithm.desired_count || 'N/A'}
                      </Typography>
                      {algorithm.version && (
                        <Typography variant="caption" display="block" color="text.secondary">
                          <strong>Version:</strong> {algorithm.version}
                        </Typography>
                      )}
                      {algorithm.category && (
                        <Typography variant="caption" display="block" color="text.secondary">
                          <strong>Category:</strong> {algorithm.category}
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
                              +{algorithm.tags.length - 3} more
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
