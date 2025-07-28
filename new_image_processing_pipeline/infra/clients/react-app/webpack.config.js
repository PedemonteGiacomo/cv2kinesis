const path = require('path');
module.exports = {
  entry: './src/index.jsx',
  output: { filename: 'bundle.js', path: path.resolve(__dirname,'dist') },
  module: {
    rules: [{
      test: /\.jsx?$/, use: 'babel-loader', exclude: /node_modules/ 
    }]
  },
  resolve: { extensions: ['.js','.jsx'] },
  devServer: { static: './dist', port: 3000 }
};
