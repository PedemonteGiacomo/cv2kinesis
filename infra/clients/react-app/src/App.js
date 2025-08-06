import React, { useState, useEffect } from 'react';
import { 
  AppBar, 
  Toolbar, 
  Typography, 
  Container, 
  Paper, 
  Box,
  Alert,
  CircularProgress,
  Card,
  CardContent,
  Chip,
  Grid
} from '@mui/material';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { Amplify } from 'aws-amplify';
import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';

import AlgorithmViewer from './components/AlgorithmViewer';
import './App.css';

// Configure Amplify (we'll get these values from environment variables)
const amplifyConfig = {
  Auth: {
    region: process.env.REACT_APP_AWS_REGION || 'us-east-1',
    userPoolId: process.env.REACT_APP_USER_POOL_ID,
    userPoolWebClientId: process.env.REACT_APP_USER_POOL_CLIENT_ID,
    authenticationFlowType: 'USER_SRP_AUTH'
  }
};

if (amplifyConfig.Auth.userPoolId && amplifyConfig.Auth.userPoolWebClientId) {
  Amplify.configure(amplifyConfig);
}

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
  const [isConfigured, setIsConfigured] = useState(false);
  const [configError, setConfigError] = useState(null);

  useEffect(() => {
    // Check if Amplify is properly configured
    if (!process.env.REACT_APP_USER_POOL_ID || !process.env.REACT_APP_USER_POOL_CLIENT_ID) {
      setConfigError('Missing Cognito configuration. Please set REACT_APP_USER_POOL_ID and REACT_APP_USER_POOL_CLIENT_ID environment variables.');
    } else {
      setIsConfigured(true);
    }
  }, []);

  const AppContent = () => (
    <Container maxWidth="lg">
      <Box sx={{ my: 4 }}>
        <Typography variant="h4" component="h1" gutterBottom>
          Medical Image Processing - Algorithm Catalog
        </Typography>
        <Typography variant="body1" color="text.secondary" paragraph>
          Visualizza algoritmi di elaborazione delle immagini mediche disponibili
        </Typography>
        <AlgorithmViewer />
      </Box>
    </Container>
  );

  if (configError) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Container maxWidth="sm">
          <Box sx={{ my: 4 }}>
            <Alert severity="error">
              {configError}
            </Alert>
            <Typography variant="body2" sx={{ mt: 2 }}>
              This application requires AWS Cognito configuration to work properly.
            </Typography>
          </Box>
        </Container>
      </ThemeProvider>
    );
  }

  if (!isConfigured) {
    return (
      <ThemeProvider theme={theme}>
        <CssBaseline />
        <Container maxWidth="sm">
          <Box sx={{ my: 4, textAlign: 'center' }}>
            <CircularProgress />
            <Typography variant="body1" sx={{ mt: 2 }}>
              Loading configuration...
            </Typography>
          </Box>
        </Container>
      </ThemeProvider>
    );
  }

  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <AppBar position="static" elevation={1}>
        <Toolbar>
          <Typography variant="h6" component="div" sx={{ flexGrow: 1 }}>
            MIP Algorithm Catalog
          </Typography>
        </Toolbar>
      </AppBar>
      
      <Authenticator>
        {({ signOut, user }) => (
          <main>
            <AppBar position="static" color="transparent" elevation={0}>
              <Toolbar>
                <Typography variant="body1" sx={{ flexGrow: 1 }}>
                  Benvenuto, {user?.username}
                </Typography>
                <button onClick={signOut}>Sign out</button>
              </Toolbar>
            </AppBar>
            <AppContent />
          </main>
        )}
      </Authenticator>
    </ThemeProvider>
  );
}

export default App;
