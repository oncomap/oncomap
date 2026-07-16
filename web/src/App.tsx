import { useEffect, useState } from "react";
import {
  Routes,
  Route,
  Navigate,
  useLocation,
  useNavigate,
  type Location,
} from "react-router-dom";
import { loadSiteData, SiteContext } from "./data";
import type { SiteData } from "./types";
import Layout from "./components/Layout";
import Modal from "./components/Modal";
import ScrollToTop from "./components/ScrollToTop";
import Landing from "./pages/Landing";
import Catalog from "./pages/Catalog";
import Dataset from "./pages/Dataset";
import About from "./pages/About";
import Stats from "./pages/Stats";
import Contact from "./pages/Contact";

// Renders the record in a dialog over whatever page opened it. Closing returns
// to that background entry, so Escape/backdrop behave like the browser's Back.
function DatasetModal() {
  const navigate = useNavigate();
  return (
    <Modal onClose={() => navigate(-1)} labelledBy="dataset-title">
      <Dataset inModal />
    </Modal>
  );
}

export default function App() {
  const [data, setData] = useState<SiteData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const location = useLocation();
  // Catalog cards navigate with state.background set; a direct visit or refresh
  // of /dataset/:id has no background and falls through to the full page.
  const background = (location.state as { background?: Location } | null)
    ?.background;

  useEffect(() => {
    loadSiteData().then(setData, (e) => setError(String(e.message || e)));
  }, []);

  if (error) {
    return (
      <Layout>
        <main className="wrap">
          <p className="resultline">{error}</p>
        </main>
      </Layout>
    );
  }
  if (!data) {
    return (
      <Layout>
        <main className="wrap">
          <p className="resultline">Loading catalog...</p>
        </main>
      </Layout>
    );
  }

  return (
    <SiteContext.Provider value={data}>
      <ScrollToTop />
      <Layout>
        <Routes location={background || location}>
          <Route path="/" element={<Landing />} />
          <Route path="/catalog" element={<Catalog />} />
          <Route path="/stats" element={<Stats />} />
          <Route path="/dataset/:id" element={<Dataset />} />
          <Route path="/about" element={<About />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
        {background && (
          <Routes>
            <Route path="/dataset/:id" element={<DatasetModal />} />
          </Routes>
        )}
      </Layout>
    </SiteContext.Provider>
  );
}
