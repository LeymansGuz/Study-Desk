(function () {
  function build(options, withInput) {
    return new Promise((resolve) => {
      const backdrop = document.createElement("div");
      backdrop.className = "modal-backdrop";
      const card = document.createElement("section");
      card.className = "modal-card";
      card.setAttribute("role", "dialog");
      card.setAttribute("aria-modal", "true");

      const title = document.createElement("h2");
      title.className = "modal-title";
      title.textContent = options.title || "Confirm";
      const message = document.createElement("p");
      message.className = "modal-message";
      message.textContent = options.message || "";

      let input = null;
      if (withInput) {
        const label = document.createElement("label");
        label.className = "modal-label";
        label.textContent = options.inputLabel || "Value";
        input = document.createElement("input");
        input.type = options.inputType || "text";
        input.className = "modal-input";
        input.autocomplete = "new-password";
        input.placeholder = options.placeholder || "";
        input.value = options.defaultValue || "";
        label.appendChild(input);
        card.append(title, message, label);
      } else {
        card.append(title, message);
      }

      const actions = document.createElement("div");
      actions.className = "modal-actions";
      const cancel = document.createElement("button");
      cancel.type = "button";
      cancel.className = "quiet-button";
      cancel.textContent = options.cancelText || "Cancel";
      const confirm = document.createElement("button");
      confirm.type = "button";
      confirm.className = options.danger ? "danger-button" : "primary-button";
      confirm.textContent = options.confirmText || "Confirm";
      if (!options.hideCancel) actions.appendChild(cancel);
      actions.appendChild(confirm);
      card.appendChild(actions);
      backdrop.appendChild(card);
      document.body.appendChild(backdrop);

      const close = (value) => {
        document.removeEventListener("keydown", onKey);
        backdrop.remove();
        if (previousFocus && typeof previousFocus.focus === "function") {
          previousFocus.focus();
        }
        resolve(value);
      };
      const previousFocus = document.activeElement;
      const focusable = () => Array.from(
        card.querySelectorAll("button, input, select, textarea, a[href]")
      ).filter((element) => !element.disabled && element.offsetParent !== null);
      const onKey = (event) => {
        if (event.key === "Escape") close(withInput ? null : false);
        if (event.key === "Enter" && withInput && event.target === input) {
          close(input.value.trim() || null);
        }
        if (event.key === "Tab") {
          const items = focusable();
          if (!items.length) return;
          const first = items[0];
          const last = items[items.length - 1];
          if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
          } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
          }
        }
      };
      if (!options.hideCancel) {
        cancel.addEventListener("click", () => close(withInput ? null : false));
      }
      confirm.addEventListener("click", () => close(withInput ? (input.value.trim() || null) : true));
      backdrop.addEventListener("click", (event) => {
        if (event.target === backdrop) close(withInput ? null : false);
      });
      document.addEventListener("keydown", onKey);
      window.setTimeout(() => (input || confirm).focus(), 0);
    });
  }

  window.appConfirm = function (message, options = {}) {
    return build({ ...options, message }, false);
  };

  window.appAlert = function (message, options = {}) {
    return build({ ...options, message, confirmText: "OK", hideCancel: true }, false);
  };

  window.appPrompt = function (message, options = {}) {
    return build({ ...options, message }, true);
  };
})();
