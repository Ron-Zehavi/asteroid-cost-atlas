interface Props {
  onClose: () => void;
}

export function AboutModal({ onClose }: Props) {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose}>x</button>

        <h2>About Asteroid Atlas</h2>

        <p>
          Artificial intelligence and robotics are beginning to remove one of humanity's oldest
          constraints: the availability of labor. As autonomous systems scale across industry,
          manufacturing, infrastructure, and energy, global production capacity can expand far
          beyond historical limits. The next bottleneck is no longer human effort—but access to
          physical resources, especially metals required for computation, electrification, space
          systems, and large-scale energy generation.
        </p>

        <p>
          Asteroid Atlas exists to help address this emerging constraint. The project maps
          the orbital accessibility, physical properties, and economic potential of millions of
          asteroids to identify realistic candidates for early space-resource missions. By
          providing transparent, reproducible, catalog-scale data tools, it supports researchers,
          engineers, and mission planners working toward the first generation of practical
          extraterrestrial mining campaigns—and contributes to accelerating humanity's transition
          from a resource-limited civilization to a space-enabled industrial economy. 🚀🛰️
        </p>

        <h3>How We Find Asteroids</h3>
        <p>
          We start with NASA's Small-Body Database containing ~1.5 million cataloged asteroids
          (JPL SSD, 2026). We enrich this with rotation periods from the Asteroid Lightcurve
          Database (Warner, Harris &amp; Pravec, 2009), thermal-infrared diameters from the
          NEOWISE survey (Mainzer et al., 2019), photometric colors from the Sloan Digital Sky
          Survey (Hasselmann et al., 2012), near-infrared colors and taxonomy from the MOVIS
          catalog (Popescu et al., 2018), and high-precision orbital elements from JPL Horizons
          for near-Earth asteroids.
        </p>

        <h3>How We Estimate What's Inside Them</h3>
        <p>
          Each asteroid is classified into a resource class—carbonaceous (water-rich), silicaceous,
          metallic, or basaltic—using a five-layer system: direct taxonomy, spectral type, SDSS
          color indices (Ivezic et al., 2001; DeMeo &amp; Carry, 2013), geometric albedo, or
          population average. Metal concentrations come from measured meteorite compositions: CI
          chondrite chemistry (Lodders, Bergemann &amp; Palme, 2025) for carbonaceous types, and
          iron meteorite PGM data (Cannon, Gialich &amp; Acain, 2023) for metallic types.
        </p>

        <h3>How We Estimate Mission Cost</h3>
        <p>
          We approximate the energy needed to reach each asteroid using a simplified Hohmann
          transfer model with inclination correction (Shoemaker &amp; Helin, 1979; Sanchez &amp;
          McInnes, 2011). Transport cost follows the Tsiolkovsky rocket equation using Falcon
          Heavy baseline pricing. The mission architecture assumes a $300M fixed cost calibrated
          from Discovery-class missions (NEAR, Hayabusa2, OSIRIS-REx) plus per-kilogram transport
          and extraction overhead (Sonter, 1997; Elvis, 2014).
        </p>

        <h3>Visualization</h3>
        <p>
          The 3D solar system is rendered with Three.js: a textured Sun and eight planets at real
          AU distances, with an <code>OBJECT_SCALE</code> exaggeration knob so the bodies stay
          visible at typical zoom levels. Asteroids are drawn as instanced textured spheres, one
          group per composition class — five visually distinct types (carbonaceous, silicate,
          metallic, basaltic, unknown) using public-domain Solar System Scope textures. The
          mission view animates a Hohmann transfer arc with a spacecraft model: <strong>Earth turns
          green during the launch window</strong>, and the <strong>selected target asteroid turns
          green at arrival</strong>. Click any asteroid or planet to focus the camera on it; a
          ring marks the active body so it's easy to track.
        </p>

        <h3>How We Score Physical Feasibility</h3>
        <p>
          Surface gravity is estimated from diameter assuming a spherical body with uniform density.
          Rotation feasibility penalizes spin rates below the 2-hour cohesionless rubble-pile limit
          (Pravec &amp; Harris, 2000). Regolith likelihood combines asteroid size and rotation
          period as independent signals for surface material retention.
        </p>

        <h3>References</h3>
        <ul className="references">
          <li>Cannon, K. M., Gialich, S., &amp; Acain, A. (2023). Accessible Precious Metals on Asteroids. <em>Planetary and Space Science</em>, 225, 105608.</li>
          <li>DeMeo, F. E., &amp; Carry, B. (2013). The Taxonomic Distribution of Asteroids. <em>Icarus</em>, 226(1), 723-741.</li>
          <li>Elvis, M. (2014). How many ore-bearing asteroids? <em>Planetary and Space Science</em>, 91, 20-26.</li>
          <li>Hasselmann, P. H., et al. (2012). SDSS-based Asteroid Taxonomy V1.1. <em>NASA PDS</em>.</li>
          <li>Ivezic, Z., et al. (2001). Solar System Objects in the SDSS. <em>AJ</em>, 122, 2749.</li>
          <li>Lodders, K., Bergemann, M., &amp; Palme, H. (2025). Solar System Abundances. <em>arXiv:2502.10575</em>.</li>
          <li>Mainzer, A. K., et al. (2019). NEOWISE Diameters and Albedos V2.0. <em>NASA PDS</em>.</li>
          <li>Popescu, M., et al. (2018). MOVIS: A near-infrared survey for asteroid taxonomy in the VISTA Hemisphere Survey. <em>A&amp;A</em>, 617, A12.</li>
          <li>Pravec, P., &amp; Harris, A. W. (2000). Fast and Slow Rotation of Asteroids. <em>Icarus</em>, 148(1), 12-20.</li>
          <li>Sanchez, J. P., &amp; McInnes, C. R. (2011). Asteroid Resource Map. <em>J. Spacecraft Rockets</em>, 48(1), 153-165.</li>
          <li>Shoemaker, E. M., &amp; Helin, E. (1979). Earth-Approaching Asteroids as Targets. <em>NASA CP-2053</em>.</li>
          <li>Sonter, M. J. (1997). Technical and Economic Feasibility of Mining NEAs. <em>Acta Astronautica</em>, 41(4-10), 637-647.</li>
          <li>Warner, B. D., Harris, A. W., &amp; Pravec, P. (2009). The asteroid lightcurve database. <em>Icarus</em>, 202(1), 134-146.</li>
        </ul>
      </div>
    </div>
  );
}
