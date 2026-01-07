import requests
import sys
import json
import time
from datetime import datetime

class GenAIIDEAPITester:
    def __init__(self, base_url="https://codex-ai-2.preview.emergentagent.com"):
        self.base_url = base_url
        self.api_url = f"{base_url}/api"
        self.session_id = f"test-session-{int(time.time())}"
        self.tests_run = 0
        self.tests_passed = 0
        self.project_id = None

    def run_test(self, name, method, endpoint, expected_status, data=None, timeout=30):
        """Run a single API test"""
        url = f"{self.api_url}/{endpoint}"
        headers = {'Content-Type': 'application/json'}

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers, timeout=timeout)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=headers, timeout=timeout)

            print(f"   Status: {response.status_code}")
            
            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                    return True, response_data
                except:
                    return True, response.text
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"   Error: {error_data}")
                except:
                    print(f"   Error: {response.text}")
                return False, {}

        except requests.exceptions.Timeout:
            print(f"❌ Failed - Request timeout after {timeout}s")
            return False, {}
        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_root_endpoint(self):
        """Test root API endpoint"""
        return self.run_test("Root API", "GET", "", 200)

    def test_code_execution_python(self):
        """Test Python code execution"""
        python_code = """
print("Hello from Python!")
result = 2 + 2
print(f"2 + 2 = {result}")
"""
        success, response = self.run_test(
            "Python Code Execution",
            "POST",
            "execute/code",
            200,
            data={"code": python_code, "language": "python"}
        )
        
        if success and 'output' in response:
            print(f"   Output: {response['output']}")
            if 'Hello from Python!' in response['output']:
                print("✅ Python execution output verified")
            else:
                print("⚠️  Python execution output unexpected")
        
        return success

    def test_code_execution_javascript(self):
        """Test JavaScript code execution"""
        js_code = """
console.log("Hello from JavaScript!");
const result = 2 + 2;
console.log(`2 + 2 = ${result}`);
"""
        success, response = self.run_test(
            "JavaScript Code Execution",
            "POST",
            "execute/code",
            200,
            data={"code": js_code, "language": "javascript"}
        )
        
        if success and 'output' in response:
            print(f"   Output: {response['output']}")
            if 'Hello from JavaScript!' in response['output']:
                print("✅ JavaScript execution output verified")
            else:
                print("⚠️  JavaScript execution output unexpected")
        
        return success

    def test_code_execution_error(self):
        """Test code execution with error"""
        error_code = "print(undefined_variable)"
        success, response = self.run_test(
            "Python Code Execution (Error)",
            "POST",
            "execute/code",
            200,
            data={"code": error_code, "language": "python"}
        )
        
        if success and 'error' in response and response['error']:
            print("✅ Error handling verified")
        elif success and 'output' in response and 'NameError' in response['output']:
            print("✅ Error in output verified")
        
        return success

    def test_ai_chat_generate(self):
        """Test AI chat for code generation"""
        success, response = self.run_test(
            "AI Chat - Code Generation",
            "POST",
            "chat/message",
            200,
            data={
                "session_id": self.session_id,
                "message": "Write a simple Python function to calculate factorial",
                "task_type": "generate"
            },
            timeout=60  # AI responses can take longer
        )
        
        if success and 'response' in response:
            print(f"   AI Response: {response['response'][:100]}...")
            if 'def' in response['response'] or 'factorial' in response['response'].lower():
                print("✅ AI generated code-related response")
            else:
                print("⚠️  AI response may not contain code")
        
        return success

    def test_ai_chat_debug(self):
        """Test AI chat for debugging"""
        buggy_code = """
def divide(a, b):
    return a / b

result = divide(10, 0)
print(result)
"""
        success, response = self.run_test(
            "AI Chat - Debug",
            "POST",
            "chat/message",
            200,
            data={
                "session_id": self.session_id,
                "message": "Debug this code",
                "code_context": buggy_code,
                "task_type": "debug"
            },
            timeout=60
        )
        
        if success and 'response' in response:
            print(f"   AI Debug Response: {response['response'][:100]}...")
            if 'zero' in response['response'].lower() or 'error' in response['response'].lower():
                print("✅ AI identified the division by zero issue")
            else:
                print("⚠️  AI may not have identified the bug")
        
        return success

    def test_chat_history(self):
        """Test chat history retrieval"""
        success, response = self.run_test(
            "Chat History",
            "GET",
            f"chat/history/{self.session_id}",
            200
        )
        
        if success and isinstance(response, list):
            print(f"   Found {len(response)} messages in history")
            if len(response) >= 2:  # Should have messages from previous tests
                print("✅ Chat history contains expected messages")
            else:
                print("⚠️  Chat history may be incomplete")
        
        return success

    def test_save_project(self):
        """Test saving a project"""
        project_data = {
            "name": f"Test Project {datetime.now().strftime('%H:%M:%S')}",
            "code": "print('Hello, World!')\nprint('This is a test project')",
            "language": "python"
        }
        
        success, response = self.run_test(
            "Save Project",
            "POST",
            "projects",
            200,
            data=project_data
        )
        
        if success and 'id' in response:
            self.project_id = response['id']
            print(f"   Project saved with ID: {self.project_id}")
            print("✅ Project saved successfully")
        
        return success

    def test_get_projects(self):
        """Test retrieving projects"""
        success, response = self.run_test(
            "Get Projects",
            "GET",
            "projects",
            200
        )
        
        if success and isinstance(response, list):
            print(f"   Found {len(response)} projects")
            if self.project_id:
                project_found = any(p.get('id') == self.project_id for p in response)
                if project_found:
                    print("✅ Previously saved project found in list")
                else:
                    print("⚠️  Previously saved project not found")
        
        return success

    def test_github_init(self):
        """Test GitHub repository initialization"""
        success, response = self.run_test(
            "GitHub Init",
            "POST",
            "github/action",
            200,
            data={
                "action": "init",
                "repo_path": f"test-repo-{int(time.time())}"
            }
        )
        
        if success and response.get('success'):
            print("✅ GitHub repository initialized")
        
        return success

    def test_github_commit(self):
        """Test GitHub commit (will fail without proper setup, but should handle gracefully)"""
        success, response = self.run_test(
            "GitHub Commit",
            "POST",
            "github/action",
            200,
            data={
                "action": "commit",
                "repo_path": f"test-repo-{int(time.time())}",
                "commit_message": "Test commit from API"
            }
        )
        
        # This might fail due to no git repo, but should return proper error
        if success:
            if response.get('success'):
                print("✅ GitHub commit successful")
            else:
                print("⚠️  GitHub commit failed (expected without proper repo setup)")
        
        return success

    def test_unsupported_language(self):
        """Test unsupported language execution"""
        success, response = self.run_test(
            "Unsupported Language",
            "POST",
            "execute/code",
            400,  # Should return 400 for unsupported language
            data={"code": "print('test')", "language": "ruby"}
        )
        
        return success

def main():
    print("🚀 Starting Gen-AI IDE API Tests")
    print("=" * 50)
    
    tester = GenAIIDEAPITester()
    
    # Run all tests
    test_methods = [
        tester.test_root_endpoint,
        tester.test_code_execution_python,
        tester.test_code_execution_javascript,
        tester.test_code_execution_error,
        tester.test_ai_chat_generate,
        tester.test_ai_chat_debug,
        tester.test_chat_history,
        tester.test_save_project,
        tester.test_get_projects,
        tester.test_github_init,
        tester.test_github_commit,
        tester.test_unsupported_language
    ]
    
    for test_method in test_methods:
        try:
            test_method()
        except Exception as e:
            print(f"❌ Test {test_method.__name__} crashed: {str(e)}")
        
        # Small delay between tests
        time.sleep(1)
    
    # Print final results
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} tests passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())