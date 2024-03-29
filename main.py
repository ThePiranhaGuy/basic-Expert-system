from knowledgebase import *
from esframework import *

def report(output):
    for inst, result in output.items():
        print('===========\nResults for %s-%d:' % (inst[0], inst[1]))
        
        for param, vals in result.items():
            possibilities = ['%s: %f' % (val[0], val[1]) for val in vals.items()]
            if len(possibilities)<1:
                print("None applicable")
                break
            print('%s with cf= %s' % (param, ', '.join(possibilities)))
        
def main():
    sh = Shell()
    define_contexts(sh)
    define_params(sh)
    define_rules(sh)
    report(sh.execute(['material']))
    
if __name__=="__main__":
    main()