import { HashRouter, Routes, Route } from 'react-router-dom';
import PropertyListPage from './pages/PropertyListPage';
import AdminPage from './pages/AdminPage';
import ViewerPage from './pages/ViewerPage';
import EditPage from './pages/EditPage';

export default function Router() {
  return (
    <HashRouter>
      <Routes>
        <Route path="/"               element={<PropertyListPage />} />
        <Route path="/admin"          element={<AdminPage />} />
        <Route path="/property/:id"   element={<ViewerPage />} />
        <Route path="/edit/:id"       element={<EditPage />} />
      </Routes>
    </HashRouter>
  );
}
