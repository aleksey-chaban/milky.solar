document.addEventListener("DOMContentLoaded", function() {
    let unlockScenario = "new-random";
    const storyContainer = document.getElementById("story-container");
    let isFetching = false;
    const scenarioButtons = document.querySelectorAll("img[data-scenario]");
    const loadingAnimation = document.getElementById("loading");

    function closeAllSelect(elmnt) {
        var x, y, i, xl, yl, arrNo = [];
        x = document.getElementsByClassName("select-items");
        y = document.getElementsByClassName("select-selected");
        xl = x.length;
        yl = y.length;
        for (i = 0; i < yl; i++) {
          if (elmnt == y[i]) {
            arrNo.push(i)
          } else {
            y[i].classList.remove("select-arrow-active");
          }
        }
        for (i = 0; i < xl; i++) {
          if (arrNo.indexOf(i)) {
            x[i].classList.add("select-hide");
          }
        }
      }

    async function fetchStory(scenario) {
        if (isFetching) return;
        isFetching = true;

        scenarioButtons.forEach(button => button.disabled = true);

        storyContainer.innerText = "";
        storyContainer.style.display = "block";

        loadingAnimation.style.display = "block";

        try {
            let response;
            if (scenario === "new") {
                response = await fetch(`/${unlockScenario}`);
                if (!response.ok) {
                    throw new Error("Story failed to generate.");
                }
                const reader = response.body.getReader();
                const decoder = new TextDecoder();

                loadingAnimation.style.display = "none";
                storyContainer.innerText = "";

                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    storyContainer.innerText += decoder.decode(value);
                }
            } else {
                response = await fetch(`/${scenario}`);
                const data = await response.json();

                loadingAnimation.style.display = "none";
                if (data.story) {
                    storyContainer.innerText = data.story;
                } else {
                    throw new Error("Error fetching story.");
                }
            }
        } catch (error) {
            loadingAnimation.style.display = "none";
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

    const input = document.getElementById("user-text");
    const counter = document.getElementById("user-counter");

    if (input && counter) {
      const maxLength = input.maxLength;

      input.addEventListener("input", function () {
          const remainingLength = input.value.length;
          counter.textContent = `${remainingLength}/${maxLength}`;
      });
    };

    const userButton = document.getElementById("user-submit");

    if (input && userButton) {
      input.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          userButton.click();
          input.value = "";
          counter.textContent = `${input.value.length}/${input.maxLength}`;
        }
      });
    }

    if (userButton) {
        userButton.addEventListener("click", async () => {
            if (isFetching) return;

            const inputValue = input.value.trim();
            const userTypeSelect = document.getElementById("user-type");
            const userTypeValue = userTypeSelect.value;

            if (!inputValue || !userTypeValue) return;

            isFetching = true;

            storyContainer.innerText = "";
            storyContainer.style.display = "block";
            loadingAnimation.style.display = "block";

            try {
                const response = await fetch("/new-user", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        userInput: inputValue,
                        userType: userTypeValue
                    })
                });

                loadingAnimation.style.display = "none";
                storyContainer.innerText = "";

                if (!response.ok) {
                    throw new Error("Story failed to generate.");
                }

                const reader = response.body.getReader();
                const decoder = new TextDecoder();

                while (true) {
                    const { value, done } = await reader.read();
                    if (done) break;
                    storyContainer.innerText += decoder.decode(value);
                }
            } catch (error) {
                loadingAnimation.style.display = "none";
                storyContainer.innerText = "An error occurred.";
                console.error(error);
            } finally {
                isFetching = false;
                input.value = "";
                counter.textContent = `0/${input.maxLength}`;
                userTypeSelect.selectedIndex = 0;
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
