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
        let errorData = null;
        
        try {
          errorData = await response.json();
          errorMessage = errorData.message || errorData.error || errorMessage;
          
          // For 409 Conflict (algorithm already exists), provide detailed error
          if (response.status === 409 && errorData.existing_algorithm) {
            const existing = errorData.existing_algorithm;
            errorMessage = `${errorData.message}\n\nExisting algorithm:\n` +
              `• ID: ${existing.algorithm_id}\n` +
              `• Status: ${existing.status}\n` +
              `• CPU: ${existing.cpu}, Memory: ${existing.memory}MB\n` +
              `• Image: ${existing.image_uri}\n\n` +
              `${errorData.suggestion}`;
          }
        } catch (e) {
          // If response is not JSON, use status text
          errorMessage = response.statusText || errorMessage;
        }
        
        const error = new Error(errorMessage);
        error.status = response.status;
        error.data = errorData;
        throw error;
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
        throw new Error('Connection error: unable to reach server');
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
  async getAlgorithm(algo_id, token = null) {
    return await this.makeRequest(`/algorithms/${algo_id}`, {
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
  async updateAlgorithm(algo_id, algorithmData, token = null) {
    return await this.makeRequest(`/algorithms/${algo_id}`, {
      method: 'PATCH',
      token,
      body: JSON.stringify(algorithmData),
    });
  }

  // Delete algorithm
  async deleteAlgorithm(algo_id, hard = false, token = null) {
    const queryParam = hard ? '?hard=true' : '';
    return await this.makeRequest(`/algorithms/${algo_id}${queryParam}`, {
      method: 'DELETE',
      token,
    });
  }

}

// Create a singleton instance
const apiService = new ApiService();
export default apiService;
