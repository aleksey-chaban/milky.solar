document.addEventListener("DOMContentLoaded", function() {
    let unlockScenario = "new-random";
    const storyContainer = document.getElementById("story-container");
    let isFetching = false;
    const scenarioButtons = document.querySelectorAll("img[data-scenario]");

    async function fetchStory(scenario) {
        if (isFetching) return;
        isFetching = true;

        scenarioButtons.forEach(button => button.disabled = true);

        storyContainer.innerText = "";
        storyContainer.style.display = "block";

        try {
            let response;
            if (scenario === "new") {
                response = await fetch(`/${unlockScenario}`);
                if (!response.ok) {
                    throw new Error("Story failed to generate.");
                }
                const reader = response.body.getReader();
                const decoder = new TextDecoder();

                storyContainer.innerText = "";

                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    storyContainer.innerText += decoder.decode(value);
                }
            } else {
                response = await fetch(`/${scenario}`);
                const data = await response.json();

                if (data.story) {
                    storyContainer.innerText = data.story;
                } else {
                    throw new Error("Error fetching story.");
                }
            }
        } catch (error) {
            storyContainer.innerText = "An error occurred.";
            console.error(error);
        } finally {
            isFetching = false;
            scenarioButtons.forEach(button => button.disabled = false);
        }
    }

    scenarioButtons.forEach(button => {
        button.addEventListener("click", () => {
            const scenario = button.getAttribute("data-scenario");
            fetchStory(scenario);
        });
    });

    const input = document.getElementById("guest-text");
    const counter = document.getElementById("guest-counter");

    if (input && counter) {
      const maxLength = input.maxLength;

      input.addEventListener("input", function () {
          const remainingLength = input.value.length;
          counter.textContent = `${remainingLength}/${maxLength}`;
      });
    };

    const guestButton = document.getElementById("guest-submit");

    if (input && guestButton) {
      input.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          guestButton.click();
          input.value = "";
          counter.textContent = `${input.value.length}/${input.maxLength}`;
        }
      });
    }

    if (guestButton) {
      guestButton.addEventListener("click", async () => {
            const inputValue = input.value.trim();
            if (!inputValue) return;
            isFetching = true;

            storyContainer.innerText = "Locating your profile";
            storyContainer.style.display = "block";

            try {
                const response = await fetch("/new-guest", {
                    method: "POST",
                    headers: {"Content-Type": "application/json"},
                    body: JSON.stringify({guestInput: inputValue})
                });

                storyContainer.innerText = "";

                if (!response.ok) {
                    throw new Error("Story failed to generate.");
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();

                while (true) {
                  const {value, done} = await reader.read();
                  if (done) break;
                  storyContainer.innerText += decoder.decode(value);
                }
            } catch (error) {
                storyContainer.innerText = "An error occurred.";
                console.error(error);
            } finally {
                isFetching = false;
            }
        });
    }

    const wolf = document.getElementById("wolf");
    let lastScrollTop = 0;
    let scrollTimeout;
    let currentDirection = "sitting";

    window.addEventListener("scroll", () => {
      let scrollTop = window.pageYOffset || document.documentElement.scrollTop;
      clearTimeout(scrollTimeout);

      if (scrollTop > lastScrollTop) {
        if (currentDirection !== "right") {
          wolf.src = animations.standUpRight;
          setTimeout(() => wolf.src = animations.walkingRight, 100);
          currentDirection = "right";
        }
      } else if (scrollTop < lastScrollTop) {
        if (currentDirection !== "left") {
          wolf.src = animations.standUpLeft;
          setTimeout(() => wolf.src = animations.walkingLeft, 100);
          currentDirection = "left";
        }
      }

      scrollTimeout = setTimeout(() => {
        if (currentDirection === "right") {
          wolf.src = animations.sitDownRight;
        } else if (currentDirection === "left") {
          wolf.src = animations.sitDownLeft;
        }
        currentDirection = "sitting";
      }, 100);

      lastScrollTop = scrollTop <= 0 ? 0 : scrollTop;
    });
});
