import com.terraformersmc.biolith.api.biome.BiolithFittestNodes;
import com.terraformersmc.biolith.impl.biome.InterfaceSearchTree;
import com.terraformersmc.biolith.impl.biome.SearchTreeTraversalStack;
import com.terraformersmc.biolith.impl.mixin.MixinSearchTree;
import com.terraformersmc.biolith.impl.mixin.ReferenceSearchTree;
import net.minecraft.registry.RegistryKey;
import net.minecraft.registry.RegistryKeys;
import net.minecraft.registry.entry.RegistryEntry;
import net.minecraft.util.Identifier;
import net.minecraft.world.biome.source.util.MultiNoiseUtil.*;
import net.minecraft.world.biome.source.util.MultiNoiseUtil.SearchTree.*;
import java.lang.reflect.Field;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.AtomicInteger;

/** Differential oracle is the pinned original Java, not a rewritten algorithm. */
@SuppressWarnings({"unchecked", "rawtypes"})
public class Differential {
    static final AtomicInteger CHECKS = new AtomicInteger();
    static int nextId;
    static class Pair {
        final InterfaceSearchTree<Object> original = new ReferenceSearchTree<>();
        final InterfaceSearchTree<Object> candidate = new MixinSearchTree<>();
        Pair(TreeNode<Object> root) throws Exception { root(original, root); root(candidate, root); }
    }
    static void check(boolean condition, String message) {
        CHECKS.incrementAndGet();
        if (!condition) throw new AssertionError(message);
    }
    static Field field(Object object, String name) throws Exception {
        Field field = object.getClass().getDeclaredField(name); field.setAccessible(true); return field;
    }
    static void root(Object search, TreeNode<Object> root) throws Exception { field(search,"firstNode").set(search,root); }
    static TreeLeafNode<Object> leaf(int biome, long... point) {
        return new TreeLeafNode<>(nextId++, new RegistryEntry<>(RegistryKey.of(RegistryKeys.BIOME,
            Identifier.of("test", "biome_" + biome))), point);
    }
    static TreeBranchNode<Object> branch(TreeNode<Object>... children) {
        long[] min = new long[3], max = new long[3];
        Arrays.fill(min,Long.MAX_VALUE); Arrays.fill(max,Long.MIN_VALUE);
        for (var child : children) for(int i=0;i<3;i++) {
            min[i]=Math.min(min[i],child.min[i]); max[i]=Math.max(max[i],child.max[i]);
        }
        if(children.length==0) { Arrays.fill(min,0); Arrays.fill(max,0); }
        return new TreeBranchNode<>(nextId++, children,min,max);
    }
    static long distance(TreeNode<Object> node, long[] point) {
        long result=0;
        for(int i=0;i<3;i++) {
            long delta=point[i]<node.min[i]?node.min[i]-point[i]:Math.max(0,point[i]-node.max[i]);
            result+=delta*delta;
        }
        return result;
    }
    static String describe(BiolithFittestNodes<Object> value) {
        return (value.ultimate()==null?-1:value.ultimate().id)+":"+value.ultimateDistance()+":"+
               (value.penultimate()==null?-1:value.penultimate().id)+":"+value.penultimateDistance();
    }
    record Outcome(BiolithFittestNodes<Object> value, Class<?> failure, List<String> visits) {}
    static Outcome run(InterfaceSearchTree<Object> search, NoiseValuePoint point, int throwAt, int recurseAt, boolean extremes) {
        List<String> visits=new ArrayList<>();
        int[] calls={0};
        try {
            var value=search.biolith$searchTreeGet(point,(node,parameters)->{
                visits.add("outer:"+node.id);
                int call=++calls[0];
                if(call==throwAt) throw new IllegalStateException("distance callback");
                if(call==recurseAt) {
                    var inner=search.biolith$searchTreeGet(new NoiseValuePoint(new long[]{17,-8,4}), (n,p)->{
                        visits.add("inner:"+n.id); return distance(n,p);
                    });
                    visits.add("result:"+describe(inner));
                }
                return extremes ? (node.id%3==0?Long.MAX_VALUE:node.id%3==1?Long.MIN_VALUE:0) : distance(node,parameters);
            });
            return new Outcome(value,null,visits);
        } catch(RuntimeException failure) { return new Outcome(null,failure.getClass(),visits); }
    }
    static void clean(Pair pair) throws Exception {
        var local=(ThreadLocal<?>)field(pair.candidate,"biolith$traversalStack").get(pair.candidate);
        Object scratch=local.get();
        check(!(boolean)field(scratch,"acquired").get(scratch),"scratch left acquired");
        for(Object value:(Object[])field(scratch,"arrays").get(scratch)) check(value==null,"retained branch");
        check((int)field(scratch,"used").get(scratch)==0,"used not reset");
    }
    static void compare(Pair pair, NoiseValuePoint point, int throwAt, int recurseAt, boolean extremes) throws Exception {
        Outcome a=run(pair.original,point,throwAt,recurseAt,extremes);
        Outcome b=run(pair.candidate,point,throwAt,recurseAt,extremes);
        check(a.failure==b.failure,"exception mismatch "+a.failure+" / "+b.failure);
        check(a.visits.equals(b.visits),"callback order mismatch");
        if(a.failure==null) {
            check(a.value.ultimate()==b.value.ultimate(),"ultimate identity mismatch");
            check(a.value.penultimate()==b.value.penultimate(),"penultimate identity mismatch");
            check(a.value.ultimateDistance()==b.value.ultimateDistance(),"ultimate distance mismatch");
            check(a.value.penultimateDistance()==b.value.penultimateDistance(),"penultimate distance mismatch");
        }
        for(String name:List.of("previousUltimateNode","previousPenultimateNode")) {
            Object x=((ThreadLocal<?>)field(pair.original,name).get(pair.original)).get();
            Object y=((ThreadLocal<?>)field(pair.candidate,name).get(pair.candidate)).get();
            check(x==y,"cached node mismatch");
        }
        clean(pair);
    }
    static NoiseValuePoint point(long x,long y,long z) { return new NoiseValuePoint(new long[]{x,y,z}); }
    static TreeNode<Object> randomTree(Random random,int count) {
        List<TreeNode<Object>> nodes=new ArrayList<>();
        for(int i=0;i<count;i++) nodes.add(leaf(random.nextInt(12),random.nextInt(201)-100,random.nextInt(201)-100,random.nextInt(201)-100));
        while(nodes.size()>1) {
            List<TreeNode<Object>> parents=new ArrayList<>();
            for(int i=0;i<nodes.size();i+=5) parents.add(branch(nodes.subList(i,Math.min(i+5,nodes.size())).toArray(TreeNode[]::new)));
            nodes=parents;
        }
        return nodes.getFirst();
    }
    static void fixedCases() throws Exception {
        var a=leaf(0,0,0,0); var same=leaf(0,0,0,0); var b=leaf(1,0,0,0); var c=leaf(2,2,0,0);
        Pair tied=new Pair(branch(branch(a,same),branch(b,c)));
        for(int i=0;i<100;i++) compare(tied,point(i%3,0,0),-1,-1,false);
        for(int call:List.of(1,2,3,5,8)) {
            Pair nested=new Pair(branch(branch(a,same),branch(b,c)));
            compare(nested,point(1,0,0),-1,call,false); // cold traversal callbacks
            compare(nested,point(2,0,0),-1,call,false); // cached-distance callbacks
            compare(nested,point(0,0,0),call,-1,false);
            compare(nested,point(1,0,0),-1,-1,false);
        }
        for(var root:Arrays.asList(a,branch(a,same),branch(),branch(branch()),(TreeNode<Object>)null)) {
            Pair pair=new Pair(root);
            compare(pair,point(0,0,0),-1,-1,false);
            compare(pair,point(1,0,0),1,-1,false);
            compare(pair,point(2,0,0),-1,-1,false);
        }
        for(int depth:List.of(63,64,65)) {
            TreeNode<Object> node=leaf(0,0,0,0);
            for(int i=0;i<depth;i++) node=branch(node);
            Pair deep=new Pair(node);
            compare(deep,point(0,0,0),-1,-1,false);
            root(deep.original,a); root(deep.candidate,a);
            compare(deep,point(0,0,0),-1,-1,false); // overflow did not poison scratch
        }
        compare(new Pair(branch(a,b,c)),point(0,0,0),-1,-1,true);
    }
    static void randomCases() throws Exception {
        Random random=new Random(0xB10117);
        for(int tree=0;tree<24;tree++) {
            Pair pair=new Pair(randomTree(random,1+random.nextInt(400)));
            for(int i=0;i<600;i++) compare(pair,point(random.nextInt(401)-200,random.nextInt(401)-200,random.nextInt(401)-200),
                i%53==0?3:-1,i%47==0?2:-1,i%71==0);
        }
    }
    static void threads() throws Exception {
        Pair pair=new Pair(randomTree(new Random(12),250));
        try(var pool=Executors.newFixedThreadPool(6)) {
            List<Future<?>> futures=new ArrayList<>();
            for(int thread=0;thread<6;thread++) {
                int seed=thread;
                futures.add(pool.submit(()->{
                    try {
                        Random random=new Random(seed);
                        for(int i=0;i<300;i++) compare(pair,point(random.nextInt(301)-150,random.nextInt(301)-150,random.nextInt(301)-150),
                            i%29==0?2:-1,i%31==0?3:-1,false);
                    } catch(Exception e) { throw new RuntimeException(e); }
                }));
            }
            for(Future<?> future:futures) future.get();
        }
    }
    static void scratch() throws Exception {
        SearchTreeTraversalStack<String> stack=new SearchTreeTraversalStack<>();
        var outer=stack.acquire(); outer.reset(0,new String[]{"a","b"});
        var nested=stack.acquire(); check(nested!=outer,"nested reused active scratch");
        nested.reset(0,new String[]{"nested"}); check(nested.next(0).equals("nested"),"nested cursor");
        nested.release(); check(outer.next(0).equals("a"),"outer cursor corrupted");
        outer.release(); check(stack.acquire()==outer,"ordinary calls not reused"); stack.release();
    }
    public static void main(String[] args) throws Exception {
        fixedCases(); randomCases(); threads(); scratch();
        System.out.println("PASS: "+CHECKS.get()+" assertions; pinned-source differential, ties/fallback, callbacks, nesting, exception cleanup, depth, threads");
    }
}
