document.addEventListener("DOMContentLoaded", function() {
    let unlockScenario = "new-random";
    const storyContainer = document.getElementById("story-container");

    async function fetchStory(scenario) {
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

                while (true) {
                    const {value, done} = await reader.read();
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
        }
    }

    document.querySelectorAll("img[data-scenario]").forEach(button => {
        button.addEventListener("click", () => {
            const scenario = button.getAttribute("data-scenario");
            fetchStory(scenario);
        });
    });
});
