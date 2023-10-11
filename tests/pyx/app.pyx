from fryhcs import Element

# 这是一个pyx样例

# pyx是一个内嵌html语法的python语法扩展，通过fryhcs将pyx语法转化为python语法
# pyx内嵌html的方式如下：
# from fryhcs.html import Element
# my_element = <div class="my-element">这是我的div</div>
# another_element = (
#   <div mt-8 hidden>
#     这是一个支持<span text-red>fryhcs</span>语法的div
#   </div>)
# 在注释和字符串中的html不会被fryhcs转化。

def FunctionComponent(props):
    # 可以直接将html赋值给变量
    content1 = <span text-cyan-500 hover:text="cyan-400"  dark="text-cyan-600">你好</span>

    # 多行html赋值的时候可以加括号:
    content2 = (
      <span class="content1">
        你好：{len(content1)}
      </span>)

    # 也可以不加括号，但等号不能作为一行的最后一个字符，等好后需要在同行有元素：
    content3 = <div id='content3'>
                 你好: <span>Mr. bad!</span>
               </div>
    # 上面例子也可看出，属性值可以是单引号括起来


    # 字符串中的html不受影响
    content4 = "这是不受影响的html：<span text-cyan-500>'你好'</span>"
    content5 = '这是不受影响的html：<span text-cyan-500>"你好"</span>'
    content6 = '''
         这是不受影响的html：
         <span text-cyan-500>
           "你好"
         </span>
         '''
    content7 = """
         这是不受影响的html：
         <span text-cyan-500>
           "你好"
         </span>
         """

    # 属性值也可以是元素，但只有组件元素的属性值可以是元素，html元素的属性值不行
    content8 = <FunctionComponent2 base=<span class="hello">hello</span>>
                属性值是html元素的div
               </FunctionComponent2>

    # self-closing的变量
    br1 = <br />
    br2 = <br/>

    # html fragment
    fragment1 = (
      <>
        <p text-black>你好</p>
        <div float="left">你也<span class='good'>好</span></div>
        over: "ok", 'good'
      </>
    )
    fragment2 = <>你好</>

    # 小于号应该能正确处理
    a = b = 5
    if a <b:
        return False
    elif  a> b:
        return False
    elif a<=b:
        return False
    elif a>=b:
        return False

    return (
    <div>
      <div @click=(increment) @keydown=(increment)
           class="class1"
           keyvalue=[foo bar](age.value):"foo bar foobar"
           hidden mt-8
           id="special-div"
           {*list1}: 'color-white color-blue'
           {**dict1}
           data-value={props['value']}(age): "value1 value2 value3">

        html中可以嵌入后端渲染的变量内容，以大括号括起来，这部分内容也可以在js中修改，后跟小括号括起来的js内容：{content1}(age.value)

        这是一个支持<span text-red>frycss</span>语法的div。下面是列表内容：
        <ul>
        { [<li name={k}>
             {f"{k}: {v}"}
           </li>
           for k, v in props.items()
           if len(k) > 5] }
        </ul>

        上述例子演示了html中嵌套python代码，python代码中又嵌套html，html中又
        嵌套python代码...其中嵌入的python代码以大括号括起来

        也可以在元素中嵌入前端的响应式内容，以类似markdown加链接的方式括起来：[初始值](age.value)
        

        "pyx中元素内部字符串中的引号是字符串的一部分，所以其中的html元素仍被解析：<div>test</div>"
        还可以有正常的html：

        <div class="normal" style={{'display':'block'}}>
          这是<span>正常内容</span>
        </div>
      </div>
      <!-- script的属性可以在js中以变量的形式直接使用，但所有属性值都是字符串，需要的话做一定转换,
           如下面的initage。-->
      <script initage={a}>
        import {signal} from 'fryhcs';

        const age = signal(parseInt(initage));

        function increment() {
            age.value ++;
        }
      </script>
    </div>)

def FunctionComponent2(props):
    mylist = ('disabled', 'hidden', 'text-cyan-50')
    myprops = {k:v for k,v in props.items() if k != 'children'}
    return (
      <div>
        <!--这是html注释，不会生成到最终前端组件中 -->
        <!--下面组件引用了另一个组件，其中使用了对dict和list的扩展语法-->
        <FunctionComponent a='1' b={1+2} {**myprops} {*mylist}:"text-cyan-50"/>
      </div>)

def FunctionComponent3(props):
    return (
     <div>
       <div>[初始值](value)</div>
       <script>
         let value = 10;

         function increment() {
             value ++;
         }
       </script>
     </div>
    )
