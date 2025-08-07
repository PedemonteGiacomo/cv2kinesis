// API Service for read-only access to algorithms
class ApiService {
  constructor() {
    // Get API base URL from environment variable or default
    this.baseUrl = process.env.REACT_APP_API_BASE_URL || 'https://your-api-gateway-url.execute-api.us-east-1.amazonaws.com/prod';
  }

  async makeRequest(endpoint, options = {}) {
    const url = `${this.baseUrl}${endpoint}`;
    
    const defaultHeaders = {
      'Content-Type': 'application/json',
    };

    // Add JWT token if provided
    if (options.token) {
      defaultHeaders['Authorization'] = `Bearer ${options.token}`;
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
        throw new Error('Connection error: unable to reach the server');
      }
      throw error;
    }
  }

  // Get all algorithms (public endpoint - no auth required)
  async getAlgorithms() {
    return await this.makeRequest('/algorithms', {
      method: 'GET',
    });
  }

  // Get single algorithm by ID (public endpoint - no auth required)
  async getAlgorithm(id) {
    return await this.makeRequest(`/algorithms/${id}`, {
      method: 'GET',
    });
  }

  // Health check
  async healthCheck() {
    return await this.makeRequest('/health', {
      method: 'GET',
    });
  }

  // Get algorithm metrics (if available)
  async getAlgorithmMetrics(id, token, timeRange = '1h') {
    return await this.makeRequest(`/algorithms/${id}/metrics?range=${timeRange}`, {
      method: 'GET',
      token,
    });
  }
}

// Create a singleton instance
const apiService = new ApiService();
export default apiService;
