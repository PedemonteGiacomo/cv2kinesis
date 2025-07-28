const path = require('path');
const HtmlWebpackPlugin = require('html-webpack-plugin');
const Dotenv = require('dotenv-webpack');
module.exports = {
  entry: './src/index.jsx',
  output: { filename: 'bundle.js', path: path.resolve(__dirname,'dist') },
  module: {
    rules: [{
      test: /\.jsx?$/, use: 'babel-loader', exclude: /node_modules/ 
    }]
  },
  resolve: {
    extensions: ['.js','.jsx'],
    fallback: {
      fs: false,
      path: require.resolve('path-browserify')
    }
  },
  devServer: { static: './dist', port: 3000 },
  plugins: [
    new Dotenv(),
    new HtmlWebpackPlugin({ template: './public/index.html' })
  ]
};
