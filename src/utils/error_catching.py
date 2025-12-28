from functools import wraps

def catch_exception(func): 
    """
    Decorator that wraps a function in a try/except block.
    Prints the function name if an exception occurs, then re-raises the exception.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try: 
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Caught an error in {func.__name__}: {e}")
            raise
    return wrapper