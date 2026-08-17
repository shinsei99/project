const STORAGE_KEY = "todo-app-items";

const form = document.getElementById("add-form");
const input = document.getElementById("todo-input");
const list = document.getElementById("todo-list");
const emptyMessage = document.getElementById("empty-message");

function loadTodos() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY)) || [];
  } catch {
    return [];
  }
}

function saveTodos(todos) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(todos));
}

let todos = loadTodos();

function render() {
  list.innerHTML = "";
  todos.forEach((todo) => {
    const li = document.createElement("li");
    li.className = "todo-item" + (todo.done ? " completed" : "");

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = todo.done;
    checkbox.addEventListener("change", () => toggleTodo(todo.id));

    const span = document.createElement("span");
    span.textContent = todo.text;

    const deleteBtn = document.createElement("button");
    deleteBtn.className = "delete-btn";
    deleteBtn.textContent = "×";
    deleteBtn.setAttribute("aria-label", "削除");
    deleteBtn.addEventListener("click", () => deleteTodo(todo.id));

    li.appendChild(checkbox);
    li.appendChild(span);
    li.appendChild(deleteBtn);
    list.appendChild(li);
  });

  emptyMessage.classList.toggle("hidden", todos.length > 0);
}

function addTodo(text) {
  todos.push({ id: Date.now(), text, done: false });
  saveTodos(todos);
  render();
}

function toggleTodo(id) {
  const todo = todos.find((t) => t.id === id);
  if (todo) {
    todo.done = !todo.done;
    saveTodos(todos);
    render();
  }
}

function deleteTodo(id) {
  todos = todos.filter((t) => t.id !== id);
  saveTodos(todos);
  render();
}

form.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = input.value.trim();
  if (!text) return;
  addTodo(text);
  input.value = "";
  input.focus();
});

render();
