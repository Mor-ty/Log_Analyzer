# Google Gemini API Setup Guide

This guide will help you set up Google Gemini API for the K8s Log Analytics application.

## Prerequisites

- Google Cloud account
- Google Cloud project with billing enabled (Gemini API requires billing)

## Step 1: Get Your Gemini API Key

1. **Visit Google AI Studio**
   - Go to [https://makersuite.google.com/app/apikey](https://makersuite.google.com/app/apikey)
   - Sign in with your Google account

2. **Create API Key**
   - Click "Create API Key" button
   - Select or create a Google Cloud project
   - Accept the terms of service
   - Copy the generated API key

3. **Enable Billing (if required)**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Select your project
   - Navigate to "Billing" → "Link a billing account"
   - Follow the prompts to enable billing

## Step 2: Configure the Application

1. **Update Environment Variables**
   
   Edit the `.env` file in the project root:
   
   ```env
   GEMINI_API_KEY=your-actual-gemini-api-key-here
   ```

2. **Backend Configuration** (if running locally)
   
   Edit `backend/.env`:
   
   ```env
   GEMINI_API_KEY=your-actual-gemini-api-key-here
   ```

3. **Docker Configuration** (if using Docker Compose)
   
   Edit `.env` in the project root:
   
   ```env
   GEMINI_API_KEY=your-actual-gemini-api-key-here
   ```

## Step 3: Test the API Key

You can test your API key using curl:

```bash
curl "https://generativelanguage.googleapis.com/v1/models?key=YOUR_API_KEY"
```

Expected response should include available models like "gemini-pro" and "gemini-pro-vision".

## Step 4: Restart the Application

If the application is already running:

```bash
# Restart Docker containers
docker compose restart backend

# Or rebuild if needed
docker compose up -d --build backend
```

## Step 5: Verify Integration

1. Upload a test log file through the UI
2. Check if the analysis includes AI-powered insights
3. Review the backend logs for any API errors

## API Key Security

- **Never commit API keys to version control**
- **Use environment variables in production**
- **Rotate API keys regularly**
- **Monitor usage in Google Cloud Console**

## Free Tier and Pricing

Gemini API offers:
- **Free tier**: 60 requests per minute for developers
- **Paid tier**: Higher limits based on usage
- **Check current pricing**: [Google AI Pricing](https://ai.google.dev/pricing)

## Troubleshooting

### "API key not valid" Error

- Verify the API key is correct
- Check if the key is enabled for your project
- Ensure billing is enabled on your Google Cloud project

### "Quota exceeded" Error

- Check your usage in Google Cloud Console
- Consider upgrading to a paid plan
- Implement rate limiting in your application

### "Model not found" Error

- Ensure you're using the correct model name ("gemini-pro")
- Check if the model is available in your region

### No Analysis Results

- Check backend logs for API errors
- Verify the API key has necessary permissions
- Test the API key manually using curl

## Model Information

The application uses the **gemini-pro** model which:
- Supports text generation and analysis
- Ideal for log analysis and anomaly detection
- Provides high-quality natural language understanding

## Alternative: Use Without API Key

The application includes a fallback rule-based analysis when Gemini API is not configured. It will still provide:
- Basic error counting and categorization
- Common error pattern detection
- Generic troubleshooting suggestions

However, for the best experience and intelligent analysis, configure the Gemini API key.

## Additional Resources

- [Google AI Studio](https://makersuite.google.com/)
- [Gemini API Documentation](https://ai.google.dev/docs)
- [Google Cloud Console](https://console.cloud.google.com/)
- [Gemini API Quickstart](https://ai.google.dev/docs/quickstart)

## Support

For issues specific to Gemini API:
- Check the [Google AI Community](https://groups.google.com/g/generative-ai-discuss)
- Review [Gemini API documentation](https://ai.google.dev/docs)
- Monitor [Google Cloud status page](https://status.cloud.google.com/)
