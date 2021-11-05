from esframework import *
def define_context(sh):
    sh.define_context(Context('material',['name','working-stress','specific gravity','cost-per-unit-strength']))

def define_params(sh):
    sh.define_param(Parameter('name','material',cls=str,ask_first=True))
    sh.define_param(Parameter('working-stress','material',cls=float,ask_first=True))
    