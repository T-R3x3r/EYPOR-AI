// Clear all query data from localStorage
// Run this in the browser console to clear old query data

console.log('Clearing all query data from localStorage...');

// Clear the specific localStorage key
localStorage.removeItem('queryFileOrganizer');

// Also clear any other related keys that might exist
const keysToRemove = [];
for (let i = 0; i < localStorage.length; i++) {
  const key = localStorage.key(i);
  if (key && (key.includes('query') || key.includes('file') || key.includes('organizer'))) {
    keysToRemove.push(key);
  }
}

keysToRemove.forEach(key => {
  localStorage.removeItem(key);
  console.log(`Removed: ${key}`);
});

console.log('All query data cleared from localStorage!');
console.log('Refresh the page to see the changes.'); 