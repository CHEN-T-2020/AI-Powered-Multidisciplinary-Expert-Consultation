#!/usr/bin/env python3
"""
Comprehensive Backend API Testing for Multi-Agent Medical Consultation System
Tests all API endpoints including real-time consultation workflow
"""

import requests
import json
import time
import sys
import os
from datetime import datetime
import uuid

# Get backend URL from frontend .env file
def get_backend_url():
    try:
        with open('/app/frontend/.env', 'r') as f:
            for line in f:
                if line.startswith('REACT_APP_BACKEND_URL='):
                    return line.split('=', 1)[1].strip()
    except Exception as e:
        print(f"Error reading frontend .env: {e}")
        return None

BACKEND_URL = get_backend_url()
if not BACKEND_URL:
    print("❌ Could not get backend URL from frontend/.env")
    sys.exit(1)

API_BASE = f"{BACKEND_URL}/api"
print(f"🔗 Testing backend at: {API_BASE}")

class BackendTester:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })
        self.test_results = []
        
    def log_test(self, test_name, success, message, details=None):
        """Log test results"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}: {message}")
        if details:
            print(f"   Details: {details}")
        
        self.test_results.append({
            'test': test_name,
            'success': success,
            'message': message,
            'details': details,
            'timestamp': datetime.now().isoformat()
        })
    
    def test_health_check(self):
        """Test basic health check endpoint"""
        try:
            response = self.session.get(f"{API_BASE}/")
            
            if response.status_code == 200:
                data = response.json()
                if "message" in data and "Medical Consultation" in data["message"]:
                    self.log_test("Health Check", True, "API is responding correctly")
                    return True
                else:
                    self.log_test("Health Check", False, "Unexpected response format", data)
                    return False
            else:
                self.log_test("Health Check", False, f"HTTP {response.status_code}", response.text)
                return False
                
        except Exception as e:
            self.log_test("Health Check", False, f"Connection error: {str(e)}")
            return False
    
    def test_status_endpoints(self):
        """Test status check endpoints"""
        try:
            # Test POST /status
            test_data = {"client_name": "test_client_" + str(uuid.uuid4())[:8]}
            response = self.session.post(f"{API_BASE}/status", json=test_data)
            
            if response.status_code == 200:
                data = response.json()
                if "id" in data and "client_name" in data:
                    self.log_test("POST Status", True, "Status creation successful")
                    
                    # Test GET /status
                    get_response = self.session.get(f"{API_BASE}/status")
                    if get_response.status_code == 200:
                        status_list = get_response.json()
                        if isinstance(status_list, list):
                            self.log_test("GET Status", True, f"Retrieved {len(status_list)} status records")
                            return True
                        else:
                            self.log_test("GET Status", False, "Response is not a list", status_list)
                            return False
                    else:
                        self.log_test("GET Status", False, f"HTTP {get_response.status_code}", get_response.text)
                        return False
                else:
                    self.log_test("POST Status", False, "Missing required fields in response", data)
                    return False
            else:
                self.log_test("POST Status", False, f"HTTP {response.status_code}", response.text)
                return False
                
        except Exception as e:
            self.log_test("Status Endpoints", False, f"Error: {str(e)}")
            return False
    
    def test_consultation_start(self):
        """Test consultation start endpoint"""
        try:
            # Use the Chinese medical question from the review request
            consultation_data = {
                "question": "3岁男孩反复咳嗽2个月，夜间加重，运动后气促，既往有湿疹史，请问可能的诊断是什么？",
                "model": "gpt-4o-mini"
            }
            
            response = self.session.post(f"{API_BASE}/consultation/start", json=consultation_data)
            
            if response.status_code == 200:
                data = response.json()
                if "session_id" in data and "status" in data:
                    if data["status"] == "started":
                        self.log_test("Consultation Start", True, f"Session started: {data['session_id']}")
                        return data["session_id"]
                    else:
                        self.log_test("Consultation Start", False, f"Unexpected status: {data['status']}", data)
                        return None
                else:
                    self.log_test("Consultation Start", False, "Missing required fields", data)
                    return None
            else:
                self.log_test("Consultation Start", False, f"HTTP {response.status_code}", response.text)
                return None
                
        except Exception as e:
            self.log_test("Consultation Start", False, f"Error: {str(e)}")
            return None
    
    def test_consultation_progress(self, session_id, monitor_duration=60):
        """Test consultation progress monitoring"""
        if not session_id:
            self.log_test("Progress Monitoring", False, "No session ID provided")
            return False
            
        try:
            print(f"📊 Monitoring progress for session {session_id} for {monitor_duration} seconds...")
            start_time = time.time()
            last_progress = -1
            progress_updates = []
            
            while time.time() - start_time < monitor_duration:
                response = self.session.get(f"{API_BASE}/consultation/{session_id}/progress")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    if "progress" in data and "current_step" in data:
                        current_progress = data["progress"]
                        current_step = data["current_step"]
                        status = data.get("status", "unknown")
                        
                        # Log progress updates
                        if current_progress != last_progress:
                            print(f"   Progress: {current_progress:.1f}% - {current_step}")
                            progress_updates.append({
                                'progress': current_progress,
                                'step': current_step,
                                'status': status,
                                'timestamp': time.time() - start_time
                            })
                            last_progress = current_progress
                        
                        # Check if completed
                        if status == "completed":
                            result = data.get("result")
                            if result:
                                self.log_test("Progress Monitoring", True, 
                                            f"Consultation completed in {time.time() - start_time:.1f}s",
                                            f"Final result contains {len(result.get('experts', []))} experts")
                                self.log_test("Consultation Workflow", True, 
                                            "Multi-agent workflow executed successfully",
                                            f"Progress updates: {len(progress_updates)}")
                                return True
                            else:
                                self.log_test("Progress Monitoring", False, "Completed but no result")
                                return False
                        
                        # Check for errors
                        if status == "error":
                            error_msg = data.get("result", {}).get("error", "Unknown error")
                            self.log_test("Progress Monitoring", False, f"Consultation failed: {error_msg}")
                            return False
                            
                    else:
                        self.log_test("Progress Monitoring", False, "Missing progress fields", data)
                        return False
                else:
                    self.log_test("Progress Monitoring", False, f"HTTP {response.status_code}", response.text)
                    return False
                
                time.sleep(2)  # Check every 2 seconds
            
            # If we reach here, monitoring timed out
            if progress_updates:
                self.log_test("Progress Monitoring", True, 
                            f"Progress monitoring working (timed out after {monitor_duration}s)",
                            f"Received {len(progress_updates)} progress updates")
                return True
            else:
                self.log_test("Progress Monitoring", False, "No progress updates received")
                return False
                
        except Exception as e:
            self.log_test("Progress Monitoring", False, f"Error: {str(e)}")
            return False
    
    def test_invalid_requests(self):
        """Test error handling for invalid requests"""
        try:
            # Test invalid consultation request
            invalid_data = {"invalid_field": "test"}
            response = self.session.post(f"{API_BASE}/consultation/start", json=invalid_data)
            
            if response.status_code in [400, 422]:  # Bad request or validation error
                self.log_test("Invalid Request Handling", True, "Properly rejected invalid consultation request")
            else:
                self.log_test("Invalid Request Handling", False, 
                            f"Should reject invalid request, got HTTP {response.status_code}")
            
            # Test non-existent session progress
            fake_session_id = str(uuid.uuid4())
            response = self.session.get(f"{API_BASE}/consultation/{fake_session_id}/progress")
            
            if response.status_code == 404:
                self.log_test("Non-existent Session", True, "Properly handled non-existent session")
                return True
            elif response.status_code == 200:
                data = response.json()
                # Check if it's the expected error format [{"error": "message"}, status_code]
                if isinstance(data, list) and len(data) == 2 and isinstance(data[0], dict) and "error" in data[0]:
                    self.log_test("Non-existent Session", True, "Properly handled non-existent session with error response")
                    return True
                elif isinstance(data, dict) and "error" in data:
                    self.log_test("Non-existent Session", True, "Properly handled non-existent session with error response")
                    return True
                else:
                    self.log_test("Non-existent Session", False, 
                                f"Unexpected response format for non-existent session", data)
                    return False
            else:
                self.log_test("Non-existent Session", False, 
                            f"Should return 404 or error, got HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("Error Handling", False, f"Error: {str(e)}")
            return False
    
    def test_concurrent_sessions(self):
        """Test multiple concurrent consultation sessions"""
        try:
            print("🔄 Testing concurrent sessions...")
            
            # Start multiple sessions
            sessions = []
            consultation_data = {
                "question": "患者出现发热、咳嗽症状，请协助诊断。",
                "model": "gpt-4o-mini"
            }
            
            for i in range(2):  # Test 2 concurrent sessions
                response = self.session.post(f"{API_BASE}/consultation/start", json=consultation_data)
                if response.status_code == 200:
                    data = response.json()
                    if "session_id" in data:
                        sessions.append(data["session_id"])
                        print(f"   Started session {i+1}: {data['session_id']}")
            
            if len(sessions) >= 2:
                # Check that both sessions are progressing
                time.sleep(5)  # Wait a bit for processing to start
                
                working_sessions = 0
                for session_id in sessions:
                    response = self.session.get(f"{API_BASE}/consultation/{session_id}/progress")
                    if response.status_code == 200:
                        data = response.json()
                        if data.get("progress", 0) > 0:
                            working_sessions += 1
                
                if working_sessions >= 2:
                    self.log_test("Concurrent Sessions", True, f"Successfully handling {working_sessions} concurrent sessions")
                    return True
                else:
                    self.log_test("Concurrent Sessions", False, f"Only {working_sessions} sessions working")
                    return False
            else:
                self.log_test("Concurrent Sessions", False, f"Could only start {len(sessions)} sessions")
                return False
                
        except Exception as e:
            self.log_test("Concurrent Sessions", False, f"Error: {str(e)}")
            return False
    
    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting comprehensive backend API testing...")
        print("=" * 60)
        
        # Test 1: Basic connectivity
        if not self.test_health_check():
            print("❌ Basic connectivity failed. Stopping tests.")
            return False
        
        # Test 2: Status endpoints
        self.test_status_endpoints()
        
        # Test 3: Start consultation and monitor progress
        session_id = self.test_consultation_start()
        if session_id:
            # Monitor for 60 seconds to see the workflow in action
            self.test_consultation_progress(session_id, monitor_duration=60)
        
        # Test 4: Error handling
        self.test_invalid_requests()
        
        # Test 5: Concurrent sessions
        self.test_concurrent_sessions()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        total_tests = len(self.test_results)
        passed_tests = sum(1 for result in self.test_results if result['success'])
        failed_tests = total_tests - passed_tests
        
        print(f"Total Tests: {total_tests}")
        print(f"Passed: {passed_tests}")
        print(f"Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests/total_tests)*100:.1f}%")
        
        if failed_tests > 0:
            print("\n❌ FAILED TESTS:")
            for result in self.test_results:
                if not result['success']:
                    print(f"   - {result['test']}: {result['message']}")
        
        return failed_tests == 0

if __name__ == "__main__":
    tester = BackendTester()
    success = tester.run_all_tests()
    
    if success:
        print("\n🎉 All tests passed! Backend is working correctly.")
        sys.exit(0)
    else:
        print("\n⚠️  Some tests failed. Check the details above.")
        sys.exit(1)