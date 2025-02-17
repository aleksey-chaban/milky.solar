document.addEventListener("DOMContentLoaded", function() {
    let unlockScenario = "new-random";
    const storyContainer = document.getElementById("story-container");

    async function fetchStory(scenario) {
        storyContainer.style.display = "none";
        storyContainer.innerText = "Loading";
        storyContainer.style.display = "block";

        try {
            let response;
            if (scenario === "new") {
                response = await fetch(`/${unlockScenario}`);
            } else {
                response = await fetch(`/${scenario}`);
            }
            const data = await response.json();
            storyContainer.style.display = "none";
            if (data.story) {
                storyContainer.innerText = data.story;
            } else {
                storyContainer.innerText = "Error fetching story.";
            };
        } catch (error) {
            storyContainer.style.display = "none";
            storyContainer.innerText = "An error occurred.";
            console.error(error);
        };

        storyContainer.style.display = "block";
    };

    document.querySelectorAll("img[data-scenario]").forEach(button => {
        button.addEventListener("click", () => {
            const scenario = button.getAttribute("data-scenario");
            fetchStory(scenario);
        });
    });
});
