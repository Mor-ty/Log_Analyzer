import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { Upload, Activity, FileText, BarChart3 } from 'lucide-react';
import './index.css';

import UploadPage from './pages/UploadPage';
import DashboardPage from './pages/DashboardPage';
import ClusterBrowserPage from './pages/ClusterBrowserPage';

function App() {
  return (
    <Router>
      <div className="min-h-screen bg-gray-900 text-gray-100">
        <nav className="bg-gray-800 border-b border-gray-700">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
            <div className="flex items-center justify-between h-16">
              <div className="flex items-center">
                <Activity className="h-8 w-8 text-blue-400" />
                <span className="ml-2 text-xl font-bold text-white">K8s Log Analytics</span>
              </div>
              <div className="flex space-x-4">
                <Link
                  to="/"
                  className="flex items-center px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition"
                >
                  <Upload className="h-4 w-4 mr-2" />
                  Upload
                </Link>
                <Link
                  to="/cluster"
                  className="flex items-center px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition"
                >
                  <FileText className="h-4 w-4 mr-2" />
                  Cluster
                </Link>
                <Link
                  to="/dashboard"
                  className="flex items-center px-3 py-2 rounded-md text-sm font-medium hover:bg-gray-700 transition"
                >
                  <BarChart3 className="h-4 w-4 mr-2" />
                  Dashboard
                </Link>
              </div>
            </div>
          </div>
        </nav>

        <main className="max-w-screen-2xl mx-auto px-4 sm:px-6 lg:px-10 py-8">
          <Routes>
            <Route path="/" element={<UploadPage />} />
            <Route path="/cluster" element={<ClusterBrowserPage />} />
            <Route path="/dashboard" element={<DashboardPage />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
