import { Routes, Route } from "react-router-dom";

import { I18nProvider } from "./i18n.jsx";
import Cursor from "./components/Cursor.jsx";
import Home from "./pages/Home.jsx";
import ProjectDetail from "./pages/ProjectDetail.jsx";
import NotFound from "./pages/NotFound.jsx";

export default function App() {
  return (
    <I18nProvider>
      <Cursor />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/work/:slug" element={<ProjectDetail />} />
        <Route path="*" element={<NotFound />} />
      </Routes>
    </I18nProvider>
  );
}
