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

    const wolf = document.getElementById("wolf-animation");
    let lastScrollTop = 0;
    let scrollTimeout;
    let currentDirection = "sitting";

    window.addEventListener("scroll", () => {
      let scrollTop = window.pageYOffset || document.documentElement.scrollTop;
      clearTimeout(scrollTimeout);

      if (scrollTop > lastScrollTop) {
        if (currentDirection !== "right") {
          wolf.src = animations.standUpRight;
          setTimeout(() => wolf.src = animations.walkingRight, 200);
          currentDirection = "right";
        }
      } else if (scrollTop < lastScrollTop) {
        if (currentDirection !== "left") {
          wolf.src = animations.standUpLeft;
          setTimeout(() => wolf.src = animations.walkingLeft, 200);
          currentDirection = "left";
        }
      }

      scrollTimeout = setTimeout(() => {
        if (currentDirection === "right") {
          wolf.src = animations.sitDownRight;
          setTimeout(() => wolf.src = animations.sitting, 200);
        } else if (currentDirection === "left") {
          wolf.src = animations.sitDownLeft;
          setTimeout(() => wolf.src = animations.sitting, 200);
        }
        currentDirection = "sitting";
      }, 200);

      lastScrollTop = scrollTop <= 0 ? 0 : scrollTop;
    });
});
