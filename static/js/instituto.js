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

    qsa(".sidebar-toggle").forEach(function (button) {
      button.addEventListener("click", function () {
        const sidebar = qs(".sidebar");
        const main = qs(".dashboard-main");
        if (sidebar) {
          sidebar.classList.toggle("active");
        }
        if (main) {
          main.classList.toggle("active");
        }
        button.classList.toggle("active");
      });
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
