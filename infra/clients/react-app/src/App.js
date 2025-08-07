import React from 'react';
import { 
  AppBar, 
  Toolbar, 
  Typography, 
  Container, 
  Box
} from '@mui/material';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';

import AlgorithmViewer from './components/AlgorithmViewer';
import './App.css';

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#2196f3',
    },
    secondary: {
      main: '#f50057',
    },
  },
});

function App() {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppBar position="static" elevation={1}>
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            MIP Algorithm Catalog
          </Typography>
          <Typography variant="body2" color="inherit">
            Catalogo Pubblico
          </Typography>
        </Toolbar>
      </AppBar>
      
      <Container maxWidth="lg">
        <Box sx={{ my: 4 }}>
          <Typography variant="h4" component="h1" gutterBottom>
            Medical Image Processing - Algorithm Catalog
          </Typography>
          <Typography variant="body1" color="text.secondary" paragraph>
            Visualizza algoritmi di elaborazione delle immagini mediche disponibili.
            Questo catalogo è pubblicamente accessibile e non richiede autenticazione.
          </Typography>
          <AlgorithmViewer />
        </Box>
      </Container>
    </ThemeProvider>
  );
}

export default App;
