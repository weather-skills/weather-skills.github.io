// Copy button for the agent hand-off prompt in the hero.
for (const block of document.querySelectorAll(".agent-handoff")) {
  const button = block.querySelector("button");
  const text = block.querySelector("code");
  const status = block.querySelector("[role=status]");
  let timer;
  button.addEventListener("click", async () => {
    let copied = true;
    try {
      await navigator.clipboard.writeText(text.textContent);
    } catch {
      copied = false;
      getSelection().selectAllChildren(text);
    }
    button.textContent = copied ? "copied" : "select";
    status.textContent = copied ? "Prompt copied" : "Copying failed; the prompt is selected, copy it yourself";
    clearTimeout(timer);
    timer = setTimeout(() => {
      button.textContent = "copy";
      status.textContent = "";
    }, 2000);
  });
}
