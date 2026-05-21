<?php
/*
Template Name: ClarityOS Layer
Description: Pure HTML layer template for Clarity OS pages.
*/
?>

<?php get_header(); ?>

<main>

<section class="layer <?php echo sanitize_title( get_the_title() ); ?>-layer">

  <header class="layer-header">
    <div class="brand-block">
      <span class="brand-title">PROFESSIONAL MEDIATIONS</span>
      <span class="brand-subtitle">The Emotional Physics Firm · <?php echo get_the_title(); ?> Layer</span>
    </div>

    <nav class="layer-nav">
      <a href="/anchor-layer" class="nav-link">ANCHOR</a>
      <a href="/orientation-layer" class="nav-link">ORIENT</a>
      <a href="/interpretation-layer" class="nav-link">INTERPRET</a>
      <a href="/inversion-layer" class="nav-link">INVERT</a>
      <a href="/integration-layer" class="nav-link">INTEGRATE</a>
      <a href="/transmission-layer" class="nav-link">TRANSMIT</a>
    </nav>
  </header>

  <div class="layer-content">
    <h2 class="layer-tag">PENTAGON POINT</h2>

    <h1 class="layer-heading">
      <?php echo get_the_title(); ?> is where meaning takes shape.
    </h1>

    <div class="layer-body">
      <?php
      while ( have_posts() ) :
        the_post();
        the_content();
      endwhile;
      ?>
    </div>

    <div class="layer-actions">
      <a href="/inversion-layer" class="btn btn-primary">NEXT</a>
      <a href="/anchor-layer" class="btn btn-secondary">RETURN TO ANCHOR</a>
    </div>

    <div class="pentagon-visual">
      <!-- Pentagon SVG or Canvas goes here -->
    </div>
  </div>

  <footer class="layer-footer">
    <div class="footer-links">
      <a href="https://www.facebook.com" target="_blank" rel="noopener">Facebook</a>
      <a href="https://www.linkedin.com" target="_blank" rel="noopener">LinkedIn</a>
    </div>

    <div class="footer-meta">
      <span>© 2026 Professional Mediations, LLC</span>
      <a href="/contact">Contact</a>
      <a href="/privacy">Privacy</a>
      <a href="/inversion-layer">Inversion Layer</a>
      <a href="/founder-ramblings">Founder Ramblings</a>
    </div>

    <div class="footer-site">
      <a href="https://pro-mediations.com">pro-mediations.com</a>
    </div>
  </footer>

</section>

</main>

<?php get_footer(); ?>