#!/usr/bin/env python3
"""
Automated Python File Executor with AI Error Fixing
Automatically executes Python files, fixes errors using AI, and retries until successful.
"""

import os
import sys
import subprocess
import tempfile
import time
import re
from typing import Tuple, Optional, Dict, Any
from pathlib import Path
import logging
from dataclasses import dataclass

# Import AI agents for error fixing
from langgraph_agent import CodeExecutorAgent

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class ExecutionResult:
    """Result of a Python file execution"""
    success: bool
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float
    error_type: Optional[str] = None
    error_message: Optional[str] = None

class AutoExecutor:
    """Automated Python file executor with AI error fixing"""
    
    def __init__(self, max_attempts: int = 5, ai_model: str = "openai"):
        self.max_attempts = max_attempts
        self.ai_model = ai_model
        self.temp_dir = tempfile.mkdtemp()
        self.execution_history = []
        
        # Initialize AI agent for error fixing
        self.ai_agent = CodeExecutorAgent(
            ai_model=ai_model,
            temp_dir=self.temp_dir,
            agent_type="code_fixer"
        )
        
        logger.info(f"AutoExecutor initialized with max_attempts={max_attempts}, ai_model={ai_model}")
        logger.info(f"Temp directory: {self.temp_dir}")
    
    def execute_python_file(self, file_path: str, timeout: int = 300) -> ExecutionResult:
        """Execute a Python file and capture the result"""
        
        start_time = time.time()
        
        try:
            # Ensure we have the absolute path
            abs_path = os.path.abspath(file_path)
            
            if not os.path.exists(abs_path):
                return ExecutionResult(
                    success=False,
                    stdout="",
                    stderr=f"File not found: {abs_path}",
                    exit_code=-1,
                    execution_time=0,
                    error_type="FileNotFoundError",
                    error_message=f"File not found: {abs_path}"
                )
            
            # Get the directory containing the file
            working_dir = os.path.dirname(abs_path)
            filename = os.path.basename(abs_path)
            
            logger.info(f"Executing: {filename} in {working_dir}")
            
            # Execute the Python file
            process = subprocess.Popen(
                [sys.executable, filename],
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout
            )
            
            stdout, stderr = process.communicate()
            execution_time = time.time() - start_time
            
            # Analyze the result
            success = process.returncode == 0 and not self._has_critical_errors(stderr)
            error_type, error_message = self._analyze_error(stderr) if not success else (None, None)
            
            result = ExecutionResult(
                success=success,
                stdout=stdout,
                stderr=stderr,
                exit_code=process.returncode,
                execution_time=execution_time,
                error_type=error_type,
                error_message=error_message
            )
            
            logger.info(f"Execution completed: success={success}, exit_code={process.returncode}, time={execution_time:.2f}s")
            
            return result
            
        except subprocess.TimeoutExpired:
            execution_time = time.time() - start_time
            logger.warning(f"Execution timed out after {timeout} seconds")
            
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=f"Execution timed out after {timeout} seconds",
                exit_code=-1,
                execution_time=execution_time,
                error_type="TimeoutError",
                error_message="Execution timed out"
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Execution failed with exception: {e}")
            
            return ExecutionResult(
                success=False,
                stdout="",
                stderr=str(e),
                exit_code=-1,
                execution_time=execution_time,
                error_type=type(e).__name__,
                error_message=str(e)
            )
    
    def _has_critical_errors(self, stderr: str) -> bool:
        """Check if stderr contains critical errors"""
        if not stderr:
            return False
        
        critical_patterns = [
            r'Error:|Exception:|Traceback',
            r'SyntaxError|NameError|ImportError|ModuleNotFoundError',
            r'AttributeError|ValueError|TypeError|KeyError',
            r'FileNotFoundError|PermissionError|OSError'
        ]
        
        for pattern in critical_patterns:
            if re.search(pattern, stderr, re.IGNORECASE):
                return True
        
        return False
    
    def _analyze_error(self, stderr: str) -> Tuple[Optional[str], Optional[str]]:
        """Analyze error output to determine error type and message"""
        if not stderr:
            return None, None
        
        # Common error patterns
        error_patterns = {
            'SyntaxError': r'SyntaxError: (.+)',
            'NameError': r'NameError: (.+)',
            'ImportError': r'ImportError: (.+)',
            'ModuleNotFoundError': r'ModuleNotFoundError: (.+)',
            'AttributeError': r'AttributeError: (.+)',
            'ValueError': r'ValueError: (.+)',
            'TypeError': r'TypeError: (.+)',
            'KeyError': r'KeyError: (.+)',
            'FileNotFoundError': r'FileNotFoundError: (.+)',
            'IndentationError': r'IndentationError: (.+)',
        }
        
        for error_type, pattern in error_patterns.items():
            match = re.search(pattern, stderr)
            if match:
                return error_type, match.group(1)
        
        # Generic error extraction
        lines = stderr.strip().split('\n')
        if lines:
            last_line = lines[-1]
            if ':' in last_line:
                parts = last_line.split(':', 1)
                if len(parts) == 2:
                    return parts[0].strip(), parts[1].strip()
        
        return "UnknownError", stderr.strip()
    
    def fix_code_with_ai(self, file_path: str, error_output: str, execution_result: ExecutionResult) -> bool:
        """Use AI to fix code errors"""
        
        try:
            logger.info(f"Attempting AI fix for {file_path}")
            
            # Read the current code
            with open(file_path, 'r', encoding='utf-8') as f:
                current_code = f.read()
            
            # Prepare error context for AI
            error_context = f"""
Fix this Python code that has execution errors:

File: {os.path.basename(file_path)}
Error Type: {execution_result.error_type}
Error Message: {execution_result.error_message}
Exit Code: {execution_result.exit_code}

STDERR Output:
{execution_result.stderr}

STDOUT Output:
{execution_result.stdout}

Original Code:
{current_code}

Please provide the corrected Python code.
"""
            
            # Use the AI agent to fix the code
            response, created_files = self.ai_agent.run(
                user_message=error_context,
                execution_output=execution_result.stdout,
                execution_error=execution_result.stderr
            )
            
            # Check if AI provided a fix
            if created_files:
                # Find the fixed file
                for created_file in created_files:
                    if created_file.endswith('.py'):
                        # Copy the fixed code back to the original file
                        fixed_file_path = os.path.join(self.temp_dir, created_file)
                        if os.path.exists(fixed_file_path):
                            with open(fixed_file_path, 'r', encoding='utf-8') as f:
                                fixed_code = f.read()
                            
                            # Create backup of original
                            backup_path = f"{file_path}.backup.{int(time.time())}"
                            with open(backup_path, 'w', encoding='utf-8') as f:
                                f.write(current_code)
                            
                            # Write fixed code
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(fixed_code)
                            
                            logger.info(f"Applied AI fix to {file_path} (backup: {backup_path})")
                            return True
            
            logger.warning("AI did not provide a code fix")
            return False
            
        except Exception as e:
            logger.error(f"AI fixing failed: {e}")
            return False
    
    def auto_execute_with_fixes(self, file_path: str, timeout: int = 300) -> Dict[str, Any]:
        """Automatically execute a file with AI error fixing until it succeeds"""
        
        logger.info(f"Starting auto-execution of {file_path}")
        
        if not os.path.exists(file_path):
            return {
                'success': False,
                'error': f"File not found: {file_path}",
                'attempts': 0,
                'execution_history': []
            }
        
        attempts = 0
        execution_history = []
        
        while attempts < self.max_attempts:
            attempts += 1
            logger.info(f"Attempt {attempts}/{self.max_attempts}")
            
            # Execute the file
            result = self.execute_python_file(file_path, timeout)
            execution_history.append({
                'attempt': attempts,
                'result': result,
                'timestamp': time.time()
            })
            
            if result.success:
                logger.info(f"✅ Execution successful on attempt {attempts}!")
                return {
                    'success': True,
                    'attempts': attempts,
                    'execution_history': execution_history,
                    'final_result': result
                }
            
            logger.warning(f"❌ Attempt {attempts} failed: {result.error_type} - {result.error_message}")
            
            # If this isn't the last attempt, try to fix with AI
            if attempts < self.max_attempts:
                logger.info("Attempting AI fix...")
                fix_applied = self.fix_code_with_ai(file_path, result.stderr, result)
                
                if not fix_applied:
                    logger.error("AI fix failed, but continuing to next attempt...")
                else:
                    logger.info("AI fix applied, retrying execution...")
        
        logger.error(f"❌ All {self.max_attempts} attempts failed")
        return {
            'success': False,
            'attempts': attempts,
            'execution_history': execution_history,
            'final_error': execution_history[-1]['result'] if execution_history else None
        }
    
    def execute_runall_or_main(self, search_directories: list = None) -> Dict[str, Any]:
        """Find and execute runall.py or main execution file"""
        
        if search_directories is None:
            search_directories = ['.', 'backend', 'src']
        
        # Look for runall.py first
        for directory in search_directories:
            runall_path = os.path.join(directory, 'runall.py')
            if os.path.exists(runall_path):
                logger.info(f"Found runall.py at {runall_path}")
                return self.auto_execute_with_fixes(runall_path)
        
        # Look for main.py
        for directory in search_directories:
            main_path = os.path.join(directory, 'main.py')
            if os.path.exists(main_path):
                logger.info(f"Found main.py at {main_path}")
                return self.auto_execute_with_fixes(main_path)
        
        # Look for any Python file with __main__ block
        logger.info("Looking for Python files with main execution block...")
        for directory in search_directories:
            if not os.path.exists(directory):
                continue
            
            for file in os.listdir(directory):
                if file.endswith('.py') and not file.startswith('test_'):
                    file_path = os.path.join(directory, file)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        if 'if __name__ == "__main__"' in content:
                            logger.info(f"Found executable Python file: {file_path}")
                            return self.auto_execute_with_fixes(file_path)
                    except Exception:
                        continue
        
        return {
            'success': False,
            'error': 'No executable Python file found (runall.py, main.py, or file with __main__)',
            'attempts': 0,
            'execution_history': []
        }
    
    def cleanup(self):
        """Clean up temporary files"""
        try:
            import shutil
            shutil.rmtree(self.temp_dir)
            logger.info(f"Cleaned up temp directory: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"Failed to clean up temp directory: {e}")


def main():
    """Main function for command-line usage"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Automatically execute Python files with AI error fixing')
    parser.add_argument('file', nargs='?', help='Python file to execute (optional)')
    parser.add_argument('--max-attempts', type=int, default=5, help='Maximum number of execution attempts')
    parser.add_argument('--timeout', type=int, default=300, help='Execution timeout in seconds')
    parser.add_argument('--ai-model', choices=['openai', 'gemini'], default='openai', help='AI model to use for fixing')
    parser.add_argument('--auto-find', action='store_true', help='Automatically find and execute runall.py or main.py')
    
    args = parser.parse_args()
    
    # Create auto executor
    executor = AutoExecutor(max_attempts=args.max_attempts, ai_model=args.ai_model)
    
    try:
        if args.auto_find or not args.file:
            # Auto-find and execute
            result = executor.execute_runall_or_main()
        else:
            # Execute specific file
            result = executor.auto_execute_with_fixes(args.file, timeout=args.timeout)
        
        # Print results
        print("\n" + "="*60)
        if result['success']:
            print("🎉 EXECUTION SUCCESSFUL!")
            print(f"✅ Completed in {result['attempts']} attempt(s)")
        else:
            print("❌ EXECUTION FAILED!")
            print(f"💥 Failed after {result['attempts']} attempt(s)")
            if 'error' in result:
                print(f"Error: {result['error']}")
        
        print("="*60)
        
        # Show execution history
        if 'execution_history' in result:
            print(f"\n📊 Execution History ({len(result['execution_history'])} attempts):")
            for entry in result['execution_history']:
                attempt = entry['attempt']
                exec_result = entry['result']
                status = "✅ SUCCESS" if exec_result.success else "❌ FAILED"
                print(f"  Attempt {attempt}: {status} ({exec_result.execution_time:.2f}s)")
                if not exec_result.success:
                    print(f"    Error: {exec_result.error_type} - {exec_result.error_message}")
        
        return 0 if result['success'] else 1
        
    finally:
        executor.cleanup()


if __name__ == "__main__":
    sys.exit(main()) 