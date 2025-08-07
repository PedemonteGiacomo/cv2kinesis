import React, { useState, useEffect } from 'react';
import { 
  AppBar, 
  Toolbar, 
  Typography, 
  Container, 
  Paper, 
  Box,
  Alert,
  CircularProgress
} from '@mui/material';
import { ThemeProvider, createTheme } from '@mui/material/styles';
import CssBaseline from '@mui/material/CssBaseline';
import { Amplify } from 'aws-amplify';
import { Authenticator } from '@aws-amplify/ui-react';
import '@aws-amplify/ui-react/styles.css';

import AlgorithmManager from './components/AlgorithmManager';
import './App.css';

// Debug: Log environment variables
console.log('Environment variables at runtime:');
console.log('REACT_APP_AWS_REGION:', process.env.REACT_APP_AWS_REGION);
console.log('REACT_APP_USER_POOL_ID:', process.env.REACT_APP_USER_POOL_ID);
console.log('REACT_APP_USER_POOL_CLIENT_ID:', process.env.REACT_APP_USER_POOL_CLIENT_ID);
console.log('REACT_APP_API_BASE_URL:', process.env.REACT_APP_API_BASE_URL);
console.log('REACT_APP_ENVIRONMENT:', process.env.REACT_APP_ENVIRONMENT);

// Configure Amplify (we'll get these values from environment variables)
const amplifyConfig = {
  Auth: {
    Cognito: {
      region: process.env.REACT_APP_AWS_REGION || 'us-east-1',
      userPoolId: process.env.REACT_APP_USER_POOL_ID,
      userPoolClientId: process.env.REACT_APP_USER_POOL_CLIENT_ID
    }
  }
};

if (amplifyConfig.Auth.Cognito.userPoolId && amplifyConfig.Auth.Cognito.userPoolClientId) {
  Amplify.configure(amplifyConfig);
}

const theme = createTheme({
  palette: {
    mode: 'light',
    primary: {
      main: '#1976d2',
    },
    secondary: {
      main: '#dc004e',
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
            MIP Admin Portal
          </Typography>
        </Toolbar>
      </AppBar>
      
      <Authenticator hideSignUp>
        {({ signOut, user }) => (
          <main>
            <AppBar position="static" color="transparent" elevation={0} sx={{ mt: 2 }}>
              <Toolbar>
                <Typography variant="body1" sx={{ flexGrow: 1 }}>
                  Welcome, {user?.username}
                </Typography>
                <button onClick={signOut}>Sign out</button>
              </Toolbar>
            </AppBar>
            <Container maxWidth="lg">
              <Box sx={{ my: 4, mt: 6 }}>
                <Typography variant="h4" component="h1" gutterBottom>
                  Medical Image Processing - Admin Portal
                </Typography>
                <Typography variant="body1" color="text.secondary" paragraph>
                  Manage medical image processing algorithms
                </Typography>
                <AlgorithmManager />
              </Box>
            </Container>
          </main>
        )}
      </Authenticator>
    </ThemeProvider>
  );
}

export default App;
