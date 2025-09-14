document.addEventListener("DOMContentLoaded", function () {
  const interactiveElements = document.querySelectorAll("[\\@action]");

  interactiveElements.forEach((element) => {
    let triggerEvent = element.getAttribute("@trigger");

    if (!triggerEvent) {
      switch (element.tagName) {
        case "FORM":
          triggerEvent = "submit";
          break;
        case "BUTTON":
          triggerEvent = "click";
          break;
        case "INPUT":
          triggerEvent = "change";
          break;
        default:
          triggerEvent = "click";
          break;
      }
    }

    element.addEventListener(triggerEvent, async function (event) {
      event.preventDefault();
      const confirmMessage = element.getAttribute("@confirm");
      if (confirmMessage) {
        if (!window.confirm(confirmMessage)) {
          return;
        }
      }
      const form = element.tagName === "FORM" ? element : element.closest("form");
      const actionAttribute = element.getAttribute("@action");
      const [method, url] = actionAttribute.split(" ");

      let requestBody = null;
      if (form) {
        requestBody = new FormData(form);
      }

      try {
        const response = await fetch(url, {
          method: method,
          body: requestBody,
        });

        if (!response.ok) {
          const errorMessage = await response.text();
          throw new Error(`Server error: ${response.status} ${errorMessage}`);
        }

        const data = await response.text();
        console.log("Success:", data);

        const targetSelector = element.getAttribute("@target");
        const swapMethod = element.getAttribute("@swap");

        if (targetSelector && swapMethod) {
          const targetElement = document.querySelector(targetSelector);
          if (targetElement) {
            if (swapMethod === "none") {
            } else if (swapMethod === "innerHTML" || swapMethod === "outerHTML") {
              targetElement[swapMethod] = data;
            } else if (["beforebegin", "afterbegin", "beforeend", "afterend"].includes(swapMethod)) {
              targetElement.insertAdjacentHTML(swapMethod, data);
            } else {
              console.error(`Unknown swap method: ${swapMethod}`);
            }
          } else {
            console.error(`Target element not found: ${targetSelector}`);
          }
        }
      } catch (error) {
        console.error("Error:", error);
      }
    });
  });
});
