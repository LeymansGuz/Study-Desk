(function () {
  try {
    const theme = localStorage.getItem("study-theme");
    if (theme === "dark" || theme === "light") {
      document.documentElement.dataset.theme = theme;
    }
  } catch (_) {
    /* localStorage may be disabled */
  }
})();
