import sys, os, pkgutil, traceback
print('cwd=', os.getcwd())
print('sys.path[0]=', sys.path[0])
print('sys.path=', sys.path)
print('exists app:', os.path.exists('app'))
print('isdir app:', os.path.isdir('app'))
loader = pkgutil.find_loader('app')
print('pkgutil.find_loader(app)=', loader)
try:
    import app
    print('imported app ok')
except Exception as e:
    print('import error:', repr(e))
    traceback.print_exc()
