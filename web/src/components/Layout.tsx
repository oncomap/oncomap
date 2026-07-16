import { NavLink, Link } from "react-router-dom";

const GITHUB = "https://github.com/oncomap/oncomap";

// Shared chrome on every route: a slim top nav + the footer ported from the
// original static page.
export default function Layout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <nav className="topnav">
        <div className="wrap topnav-inner">
          <Link to="/" className="brand">
            OncoMap
          </Link>
          <div className="topnav-links">
            <NavLink to="/catalog">Catalog</NavLink>
            <NavLink to="/stats">Stats</NavLink>
            <NavLink to="/about">About</NavLink>
            <NavLink to="/contact">Contact</NavLink>
          </div>
        </div>
      </nav>
      {children}
      <footer className="footer">
        <Link to="/contact">Contact</Link> &middot; source and curation trust
        gate on{" "}
        <a href={GITHUB} target="_blank" rel="noopener noreferrer">
          GitHub
        </a>
        . Data CC-BY-4.0 &middot; Code MIT.
      </footer>
    </>
  );
}
