import { Config } from "./config";

console.log("Testing connection to Memory Server...");
console.log(`URL: ${Config.MEMORY_API_URL}`);

const testSearch = async () => {
  try {
    console.log("Attempting search...");
    const response = await fetch(`${Config.MEMORY_API_URL}/search`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: "hello", limit: 1 }),
    });

    console.log(`Status: ${response.status}`);
    console.log(`StatusText: ${response.statusText}`);
    
    if (response.ok) {
      const data = await response.json();
      console.log("Response Data:", JSON.stringify(data, null, 2));
    } else {
      console.log("Response Text:", await response.text());
    }
  } catch (error) {
    console.error("Connection Error:", error);
  }
};

testSearch();
