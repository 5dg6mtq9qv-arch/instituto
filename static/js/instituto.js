(function () {
  function qs(selector) {
    return document.querySelector(selector);
  }

  function qsa(selector, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(selector));
  }

  const datePickerLocale = {
    weekdays: {
      shorthand: ["Dom", "Lun", "Mar", "Mie", "Jue", "Vie", "Sab"],
      longhand: ["Domingo", "Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado"]
    },
    months: {
      shorthand: ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"],
      longhand: [
        "Enero",
        "Febrero",
        "Marzo",
        "Abril",
        "Mayo",
        "Junio",
        "Julio",
        "Agosto",
        "Septiembre",
        "Octubre",
        "Noviembre",
        "Diciembre"
      ]
    },
    firstDayOfWeek: 1,
    rangeSeparator: " a ",
    weekAbbreviation: "Sem",
    scrollTitle: "Desplazar para cambiar",
    toggleTitle: "Clic para cambiar",
    amPM: ["AM", "PM"],
    yearAriaLabel: "Anio",
    monthAriaLabel: "Mes",
    hourAriaLabel: "Hora",
    minuteAriaLabel: "Minuto"
  };

  function initDatePickers(root) {
    if (!window.flatpickr) {
      return;
    }

    qsa("input.js-date-picker", root).forEach(function (input) {
      if (input._flatpickr) {
        return;
      }

      flatpickr(input, {
        allowInput: true,
        altFormat: "d/m/Y",
        altInput: true,
        altInputClass: "form-control flatpickr-display-input",
        ariaDateFormat: "d/m/Y",
        dateFormat: "Y-m-d",
        disableMobile: true,
        locale: datePickerLocale,
        monthSelectorType: "static",
        nextArrow: '<i class="ri-arrow-right-s-line"></i>',
        prevArrow: '<i class="ri-arrow-left-s-line"></i>',
        onReady: function (_, __, instance) {
          instance.calendarContainer.classList.add("instituto-date-calendar");
        }
      });
    });
  }

  function closeMobileSidebar() {
    document.body.classList.remove("overlay-active");
    const sidebar = qs(".sidebar");
    if (sidebar) {
      sidebar.classList.remove("sidebar-open");
    }
  }

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
    qsa(".theme-toggle-btn i").forEach(function (icon) {
      icon.classList.toggle("ri-moon-line", theme === "dark");
      icon.classList.toggle("ri-sun-line", theme !== "dark");
    });
  }

  window.InstitutoDatePicker = {
    init: initDatePickers
  };

  document.addEventListener("DOMContentLoaded", function () {
    const savedTheme = localStorage.getItem("theme") || "light";
    applyTheme(savedTheme);
    initDatePickers(document);

    qsa(".sidebar-mobile-toggle").forEach(function (button) {
      button.addEventListener("click", function () {
        const sidebar = qs(".sidebar");
        if (sidebar) {
          sidebar.classList.add("sidebar-open");
          document.body.classList.add("overlay-active");
        }
      });
    });

    qsa(".sidebar-close-btn, .instituto-overlay").forEach(function (element) {
      element.addEventListener("click", closeMobileSidebar);
    });

    const desktopSidebarQuery = window.matchMedia("(min-width: 1200px)");
    const sidebar = qs(".sidebar");
    const dashboardMain = qs(".dashboard-main");
    const sidebarToggles = qsa(".sidebar-toggle");

    function setSidebarCollapsed(collapsed, remember) {
      const shouldCollapse = collapsed && desktopSidebarQuery.matches;
      if (sidebar) {
        sidebar.classList.toggle("active", shouldCollapse);
      }
      if (dashboardMain) {
        dashboardMain.classList.toggle("active", shouldCollapse);
      }
      sidebarToggles.forEach(function (button) {
        button.classList.toggle("active", shouldCollapse);
        button.setAttribute("aria-pressed", shouldCollapse ? "true" : "false");
        button.setAttribute("aria-label", shouldCollapse ? "Expandir menu" : "Contraer menu");
        button.title = shouldCollapse ? "Expandir menu" : "Contraer menu";
      });
      if (remember) {
        localStorage.setItem("institutoSidebarCollapsed", collapsed ? "true" : "false");
      }
    }

    setSidebarCollapsed(localStorage.getItem("institutoSidebarCollapsed") === "true", false);

    sidebarToggles.forEach(function (button) {
      button.addEventListener("click", function () {
        setSidebarCollapsed(!sidebar.classList.contains("active"), true);
      });
    });

    desktopSidebarQuery.addEventListener("change", function () {
      setSidebarCollapsed(localStorage.getItem("institutoSidebarCollapsed") === "true", false);
    });

    qsa(".sidebar-menu .dropdown > a").forEach(function (link) {
      link.addEventListener("click", function (event) {
        event.preventDefault();
        const item = link.parentElement;
        const submenu = item ? item.querySelector(".sidebar-submenu") : null;
        if (!item || !submenu) {
          return;
        }

        qsa(".sidebar-menu .dropdown.open").forEach(function (openItem) {
          if (openItem === item) {
            return;
          }
          openItem.classList.remove("open");
          const openSubmenu = openItem.querySelector(".sidebar-submenu");
          if (openSubmenu) {
            openSubmenu.style.display = "none";
          }
          const openLink = openItem.querySelector(":scope > a");
          if (openLink) {
            openLink.setAttribute("aria-expanded", "false");
          }
        });

        const isOpen = item.classList.toggle("open");
        submenu.style.display = isOpen ? "block" : "none";
        link.setAttribute("aria-expanded", isOpen ? "true" : "false");
      });
    });

    qsa(".theme-toggle-btn").forEach(function (button) {
      button.addEventListener("click", function () {
        const currentTheme = document.documentElement.getAttribute("data-theme") || "light";
        applyTheme(currentTheme === "dark" ? "light" : "dark");
      });
    });

    qsa("[data-row-url]").forEach(function (row) {
      function openRow() {
        const url = row.getAttribute("data-row-url");
        if (url) {
          window.location.assign(url);
        }
      }

      row.addEventListener("click", function (event) {
        if (event.target.closest("a, button, input, select, textarea, label")) {
          return;
        }
        openRow();
      });

      row.addEventListener("keydown", function (event) {
        if (event.key === "Enter" && !event.target.closest("a, button, input, select, textarea")) {
          event.preventDefault();
          openRow();
        }
      });
    });

    qsa(".toggle-password").forEach(function (button) {
      button.addEventListener("click", function () {
        const input = button.parentElement ? button.parentElement.querySelector(".password-field") : null;
        if (!input) {
          return;
        }
        const showPassword = input.type === "password";
        input.type = showPassword ? "text" : "password";
        button.classList.toggle("ri-eye-line", !showPassword);
        button.classList.toggle("ri-eye-off-line", showPassword);
      });
    });
  });
})();
