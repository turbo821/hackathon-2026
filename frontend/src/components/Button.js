export function Button(text, onClick) {
  const btn = document.createElement('button')
  btn.className = 'px-4 py-2 rounded bg-blue-600 text-white hover:bg-blue-500'
  btn.textContent = text
  btn.addEventListener('click', onClick)
  return btn
}