// API Service for communicating with the MIP Admin API
import { fetchAuthSession } from 'aws-amplify/auth';

class ApiService {
  constructor() {
    // Get API base URL from environment variable or default
    let baseUrl = process.env.REACT_APP_API_BASE_URL || 'https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod';
    
    // Remove trailing slash if present
    baseUrl = baseUrl.endsWith('/') ? baseUrl.slice(0, -1) : baseUrl;
    
    // Add admin prefix to the base URL
    this.baseUrl = `${baseUrl}/admin`;
  }

  async getAuthToken() {
    try {
      const session = await fetchAuthSession();
      return session.tokens.accessToken.toString();
    } catch (error) {
      console.error('Failed to get auth token:', error);
      throw new Error('Authentication required');
    }
  }

  async makeRequest(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    
    const defaultHeaders = {
      'Content-Type': 'application/json',
    };

    // Get JWT token - use provided token or fetch from Amplify
    let token = options.token;
    if (!token) {
      try {
        token = await this.getAuthToken();
      } catch (error) {
        throw new Error('Authentication required: ' + error.message);
      }
    }

    if (token) {
      defaultHeaders['Authorization'] = `Bearer ${token}`;
    }

    const requestOptions = {
      ...options,
      headers: {
        ...defaultHeaders,
        ...options.headers,
      },
    };

    try {
      const response = await fetch(url, requestOptions);
      
      if (!response.ok) {
        let errorMessage = `HTTP ${response.status}`;
        try {
          const errorData = await response.json();
          errorMessage = errorData.message || errorData.error || errorMessage;
        } catch (e) {
          // If response is not JSON, use status text
          errorMessage = response.statusText || errorMessage;
        }
        throw new Error(errorMessage);
      }

      // Handle empty responses
      const contentType = response.headers.get('content-type');
      if (contentType && contentType.includes('application/json')) {
        return await response.json();
      } else {
        return {};
      }
    } catch (error) {
      if (error.name === 'TypeError' && error.message.includes('fetch')) {
        throw new Error('Errore di connessione: impossibile raggiungere il server');
      }
      throw error;
    }
  }

  // Get all algorithms
  async getAlgorithms(token = null) {
    return await this.makeRequest('/algorithms', {
      method: 'GET',
      token,
    });
  }

  // Get single algorithm by ID
  async getAlgorithm(id, token = null) {
    return await this.makeRequest(`/algorithms/${id}`, {
      method: 'GET',
      token,
    });
  }

  // Create new algorithm
  async createAlgorithm(algorithmData, token = null) {
    return await this.makeRequest('/algorithms', {
      method: 'POST',
      token,
      body: JSON.stringify(algorithmData),
    });
  }

  // Update existing algorithm
  async updateAlgorithm(id, algorithmData, token = null) {
    return await this.makeRequest(`/algorithms/${id}`, {
      method: 'PATCH',
      token,
      body: JSON.stringify(algorithmData),
    });
  }

  // Delete algorithm
  async deleteAlgorithm(id, token = null) {
    return await this.makeRequest(`/algorithms/${id}`, {
      method: 'DELETE',
      token,
    });
  }

  // Get algorithm status
  async getAlgorithmStatus(id, token = null) {
    return await this.makeRequest(`/algorithms/${id}/status`, {
      method: 'GET',
      token,
    });
  }

  // Start/stop algorithm
  async toggleAlgorithm(id, action, token = null) {
    return await this.makeRequest(`/algorithms/${id}/${action}`, {
      method: 'POST',
      token,
    });
  }

  // Get algorithm logs
  async getAlgorithmLogs(id, token = null, limit = 100) {
    return await this.makeRequest(`/algorithms/${id}/logs?limit=${limit}`, {
      method: 'GET',
      token,
    });
  }

  // Health check
  async healthCheck() {
    return await this.makeRequest('/health', {
      method: 'GET',
    });
  }

  // Get algorithm metrics
  async getAlgorithmMetrics(id, token = null, timeRange = '1h') {
    return await this.makeRequest(`/algorithms/${id}/metrics?range=${timeRange}`, {
      method: 'GET',
      token,
    });
  }

  // Test algorithm endpoint
  async testAlgorithm(id, testData, token = null) {
    return await this.makeRequest(`/algorithms/${id}/test`, {
      method: 'POST',
      token,
      body: JSON.stringify(testData),
    });
  }
}

// Create a singleton instance
const apiService = new ApiService();
export default apiService;
