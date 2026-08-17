const USERS_KEY = "todo-app-users";
const SESSION_KEY = "todo-app-session";

function itemsKeyFor(username) {
  return `todo-app-items::${username}`;
}

// --- auth screens ---
const authScreen = document.getElementById("auth-screen");
const appScreen = document.getElementById("app-screen");
const tabLogin = document.getElementById("tab-login");
const tabRegister = document.getElementById("tab-register");
const loginForm = document.getElementById("login-form");
const registerForm = document.getElementById("register-form");
const authError = document.getElementById("auth-error");
const currentUserLabel = document.getElementById("current-user");
const logoutBtn = document.getElementById("logout-btn");

// --- todo screen ---
const form = document.getElementById("add-form");
const input = document.getElementById("todo-input");
const list = document.getElementById("todo-list");
const emptyMessage = document.getElementById("empty-message");

let todos = [];
let currentUser = null;

function showAuthError(message) {
  authError.textContent = message;
  authError.classList.remove("hidden");
}

function clearAuthError() {
  authError.textContent = "";
  authError.classList.add("hidden");
}

function switchAuthTab(tab) {
  clearAuthError();
  const showLogin = tab === "login";
  tabLogin.classList.toggle("active", showLogin);
  tabRegister.classList.toggle("active", !showLogin);
  loginForm.classList.toggle("hidden", !showLogin);
  registerForm.classList.toggle("hidden", showLogin);
}

function loadUsers() {
  try {
    return JSON.parse(localStorage.getItem(USERS_KEY)) || {};
  } catch {
    return {};
  }
}

function saveUsers(users) {
  localStorage.setItem(USERS_KEY, JSON.stringify(users));
}

function bufferToHex(buffer) {
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}

async function hashPassword(password, saltHex) {
  const encoder = new TextEncoder();
  const data = encoder.encode(saltHex + password);
  const digest = await crypto.subtle.digest("SHA-256", data);
  return bufferToHex(digest);
}

function randomSalt() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  return bufferToHex(bytes.buffer);
}

async function registerUser(username, password) {
  const users = loadUsers();
  if (users[username]) {
    throw new Error("そのユーザー名はすでに使われています");
  }
  const salt = randomSalt();
  const hash = await hashPassword(password, salt);
  users[username] = { salt, hash };
  saveUsers(users);
}

async function verifyUser(username, password) {
  const users = loadUsers();
  const record = users[username];
  if (!record) return false;
  const hash = await hashPassword(password, record.salt);
  return hash === record.hash;
}

function setSession(username) {
  localStorage.setItem(SESSION_KEY, username);
}

function clearSession() {
  localStorage.removeItem(SESSION_KEY);
}

function getSession() {
  return localStorage.getItem(SESSION_KEY);
}

// --- todo logic (per logged-in user) ---
function loadTodos(username) {
  try {
    return JSON.parse(localStorage.getItem(itemsKeyFor(username))) || [];
  } catch {
    return [];
  }
}

function saveTodos() {
  localStorage.setItem(itemsKeyFor(currentUser), JSON.stringify(todos));
}

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
  saveTodos();
  render();
}

function toggleTodo(id) {
  const todo = todos.find((t) => t.id === id);
  if (todo) {
    todo.done = !todo.done;
    saveTodos();
    render();
  }
}

function deleteTodo(id) {
  todos = todos.filter((t) => t.id !== id);
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

// --- screen transitions ---
function enterApp(username) {
  currentUser = username;
  setSession(username);
  todos = loadTodos(username);
  currentUserLabel.textContent = `${username} さん`;
  authScreen.classList.add("hidden");
  appScreen.classList.remove("hidden");
  render();
}

function backToLogin() {
  currentUser = null;
  todos = [];
  clearSession();
  loginForm.reset();
  registerForm.reset();
  switchAuthTab("login");
  appScreen.classList.add("hidden");
  authScreen.classList.remove("hidden");
}

tabLogin.addEventListener("click", () => switchAuthTab("login"));
tabRegister.addEventListener("click", () => switchAuthTab("register"));

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearAuthError();
  const username = document.getElementById("login-username").value.trim();
  const password = document.getElementById("login-password").value;
  if (!username || !password) return;

  const ok = await verifyUser(username, password);
  if (!ok) {
    showAuthError("ユーザー名またはパスワードが正しくありません");
    return;
  }
  loginForm.reset();
  enterApp(username);
});

registerForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  clearAuthError();
  const username = document.getElementById("register-username").value.trim();
  const password = document.getElementById("register-password").value;
  if (!username || !password) return;
  if (password.length < 4) {
    showAuthError("パスワードは4文字以上にしてください");
    return;
  }

  try {
    await registerUser(username, password);
  } catch (err) {
    showAuthError(err.message);
    return;
  }
  registerForm.reset();
  enterApp(username);
});

logoutBtn.addEventListener("click", () => {
  backToLogin();
});

// --- boot ---
(function boot() {
  const session = getSession();
  const users = loadUsers();
  if (session && users[session]) {
    enterApp(session);
  } else {
    clearSession();
    switchAuthTab("login");
  }
})();
